"""Byte-determinism tests for the plan-injection surfaces (issue #210).

The question behind issue #210: does re-injecting plan context every turn
break prompt caching? The canonical injection script answers it by being
byte-deterministic — identical stdout for identical on-disk state — and by a
sed pass (v2.40) that normalizes wall-clock times in the injected progress.md
tail so the KV-cache prefix stays warm across turns.

The suite proved byte-stability for ledger-summary.sh (test_ledger.py) but
never for inject-plan.sh itself, and the two dedicated IDE hooks under
.cursor/hooks/ and .codex/hooks/ emitted the raw progress tail WITHOUT the
normalization until the fix this file pins.

Covers:
  * inject-plan.sh fired twice against an untouched fixture is byte-identical
    in every context (userprompt / pretool / precompact), in smart mode
    (PWF_INJECT=smart), when attested (including the Plan-SHA256 line), and in
    autonomous mode (ledger summary instead of the raw progress tail).
  * pretool output is unaffected by a progress.md append — this is the block
    that fires most often, so its stability matters most.
  * userprompt DOES change after a progress.md append. That is intent, not a
    bug: the tail is fresh context, only its timestamps are frozen.
  * No raw wall-clock time survives into injected output on any of the three
    routes: scripts/inject-plan.sh, .cursor/hooks/user-prompt-submit.sh,
    .codex/hooks/user-prompt-submit.sh. The two dedicated hooks are exercised
    against a legacy-root fixture (task_plan.md / progress.md at the fixture
    root): the cursor hook reads only ./task_plan.md, and the codex hook falls
    back to the root files when no .planning/ dir exists (its resolver shim
    finds nothing to resolve).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
INJECT_PLAN = SCRIPTS_DIR / "inject-plan.sh"
ATTEST_PLAN = SCRIPTS_DIR / "attest-plan.sh"
CURSOR_HOOK = REPO_ROOT / ".cursor" / "hooks" / "user-prompt-submit.sh"
CODEX_HOOK = REPO_ROOT / ".codex" / "hooks" / "user-prompt-submit.sh"

CONTEXTS = ("userprompt", "pretool", "precompact")

# A phase-structured plan so PWF_INJECT=smart takes the smart-extract path
# instead of silently falling back to head-N (which would make the smart test
# a duplicate of the legacy one).
PLAN_CONTENT = (
    "# Determinism Fixture Plan\n"
    "\n"
    "## Goal\n"
    "Prove injection is byte-stable.\n"
    "\n"
    "## Phases\n"
    "### Phase 1: Setup\n"
    "- **Status:** complete\n"
    "\n"
    "### Phase 2: Build\n"
    "- **Status:** in_progress\n"
    "\n"
    "### Phase 3: Test\n"
    "- **Status:** pending\n"
    "\n"
    "## Decisions Made\n"
    "| # | Decision |\n"
    "|---|----------|\n"
    "| 1 | Normalize timestamps |\n"
)

# The RAWPROGRESS marker lets the autonomous test assert the raw tail is NOT
# injected; the timestamps exercise the v2.40 normalization in legacy mode.
PROGRESS_CONTENT = (
    "## Session RAWPROGRESS\n"
    "- worked at 2026-08-01T11:02:55Z\n"
    "- and again at 2026-08-01T09:16:03.221Z\n"
)


def have_sh() -> bool:
    return shutil.which("sh") is not None


def scrubbed_env(**overrides: str) -> dict[str, str]:
    """Copy of the environment with every plan-affecting variable removed.

    The developer's own shell may carry PLAN_ID (resolution override),
    PLANNING_DISABLED (kills injection outright), PWF_INJECT (smart shape),
    or PWF_SESSION_ID (codex session guard) — any of which would silently
    change what these tests measure.
    """
    env = os.environ.copy()
    for var in ("PLAN_ID", "PLANNING_DISABLED", "PWF_INJECT", "PWF_SESSION_ID"):
        env.pop(var, None)
    env.update(overrides)
    return env


@unittest.skipUnless(have_sh(), "sh not available on this platform")
class SlugFixtureBase(unittest.TestCase):
    """Slug-mode fixture (.planning/<slug>/) pinned via .active_plan."""

    SLUG = "2026-08-01-determinism"

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="pwf-determinism-"))
        # Private SHA cache + HOME so attested runs never touch (or read) the
        # developer's real ~/.cache/pwf-sha.
        self.cache_dir = self.tmp / "_xdg_cache"
        self.cache_dir.mkdir()
        self.home_dir = self.tmp / "_home"
        self.home_dir.mkdir()
        self.env = scrubbed_env(
            XDG_CACHE_HOME=str(self.cache_dir),
            HOME=str(self.home_dir),
        )
        self.plan_dir = self.tmp / ".planning" / self.SLUG
        self.plan_dir.mkdir(parents=True)
        (self.tmp / ".planning" / ".active_plan").write_text(
            f"{self.SLUG}\n", encoding="utf-8"
        )
        (self.plan_dir / "task_plan.md").write_text(PLAN_CONTENT, encoding="utf-8")
        (self.plan_dir / "progress.md").write_text(PROGRESS_CONTENT, encoding="utf-8")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def inject(self, context: str, **env_overrides: str):
        env = dict(self.env)
        env.update(env_overrides)
        return subprocess.run(
            ["sh", str(INJECT_PLAN), f"--context={context}"],
            cwd=str(self.tmp),
            text=True,
            encoding="utf-8",
            capture_output=True,
            env=env,
            check=False,
        )

    def attest(self):
        return subprocess.run(
            ["sh", str(ATTEST_PLAN)],
            cwd=str(self.tmp),
            text=True,
            encoding="utf-8",
            capture_output=True,
            env=self.env,
            check=False,
        )

    def assert_twice_identical(self, context: str, **env_overrides: str) -> str:
        """Fire the context twice against untouched state; return the stdout."""
        first = self.inject(context, **env_overrides)
        second = self.inject(context, **env_overrides)
        self.assertEqual(0, first.returncode, first.stderr)
        self.assertEqual(0, second.returncode, second.stderr)
        self.assertEqual(
            first.stdout,
            second.stdout,
            f"--context={context} must be byte-identical across two fires "
            f"against an untouched plan (KV-cache hygiene)",
        )
        return first.stdout


class InjectByteStabilityTests(SlugFixtureBase):
    def test_every_context_byte_identical_untouched(self) -> None:
        # Marker assertions guard against a vacuous pass: an empty stdout is
        # trivially equal to itself, so each context must prove it injected.
        markers = {
            "userprompt": "ACTIVE PLAN",
            "pretool": "PLAN DATA",
            "precompact": "PreCompact",
        }
        for context in CONTEXTS:
            with self.subTest(context=context):
                stdout = self.assert_twice_identical(context)
                self.assertIn(markers[context], stdout)

    def test_smart_mode_byte_identical(self) -> None:
        for context in CONTEXTS:
            with self.subTest(context=context):
                stdout = self.assert_twice_identical(context, PWF_INJECT="smart")
                if context == "userprompt":
                    # Proof the smart-extract path actually engaged (a head-N
                    # fallback would not synthesize the phase count line). The
                    # fixture keeps one phase complete: with zero complete the
                    # current awk renders the count as an empty string, which
                    # is inject-plan.sh's business, not this test's.
                    self.assertIn("phases: 1/3 complete", stdout)

    def test_attested_byte_identical_including_sha_line(self) -> None:
        result = self.attest()
        self.assertEqual(0, result.returncode, result.stderr)
        for context in CONTEXTS:
            with self.subTest(context=context):
                stdout = self.assert_twice_identical(context)
                if context == "userprompt":
                    self.assertIn("Plan-SHA256: ", stdout)
                if context == "precompact":
                    self.assertIn("Plan-SHA256 at compaction:", stdout)

    def test_autonomous_mode_byte_identical_ledger_summary(self) -> None:
        # Autonomous mode requires an attested plan, otherwise injection is
        # refused (also deterministic, but not what this test measures).
        result = self.attest()
        self.assertEqual(0, result.returncode, result.stderr)
        (self.plan_dir / ".mode").write_text("autonomous\n", encoding="utf-8")

        stdout = self.assert_twice_identical("userprompt")
        self.assertIn("=== ledger summary ===", stdout)
        self.assertIn("=== RUN LEDGER ===", stdout)
        # The structured summary REPLACES the raw progress tail (security A1.5).
        self.assertNotIn("RAWPROGRESS", stdout)

        # Per-tool-call injection is dropped entirely in autonomous mode
        # (recitation policy) — trivially byte-stable, pinned anyway.
        pretool = self.assert_twice_identical("pretool")
        self.assertEqual("", pretool.strip())

    def test_pretool_unaffected_by_progress_append(self) -> None:
        # The pretool block fires before every tool call — the hottest path.
        # Progress churn between tool calls must not perturb it.
        first = self.inject("pretool")
        self.assertEqual(0, first.returncode, first.stderr)
        self.assertIn("PLAN DATA", first.stdout)

        with (self.plan_dir / "progress.md").open("a", encoding="utf-8") as f:
            f.write("- appended between tool calls\n")

        second = self.inject("pretool")
        self.assertEqual(0, second.returncode, second.stderr)
        self.assertEqual(
            first.stdout,
            second.stdout,
            "pretool injection must not change when progress.md is appended",
        )

    def test_userprompt_changes_after_progress_append(self) -> None:
        # Documents intent: the userprompt tail is fresh context by design.
        # Only its wall-clock times are frozen, not its content.
        first = self.inject("userprompt")
        self.assertEqual(0, first.returncode, first.stderr)
        self.assertNotIn("APPEND-MARKER-XYZ", first.stdout)

        with (self.plan_dir / "progress.md").open("a", encoding="utf-8") as f:
            f.write("- APPEND-MARKER-XYZ new work landed\n")

        second = self.inject("userprompt")
        self.assertEqual(0, second.returncode, second.stderr)
        self.assertNotEqual(
            first.stdout,
            second.stdout,
            "userprompt injection is supposed to pick up new progress lines",
        )
        self.assertIn("APPEND-MARKER-XYZ", second.stdout)


# Loads the Hermes plugin package (its directory name has a dash, so it is not
# importable by name) and prints the injection it would build for cwd.
_HERMES_PROBE = f"""
import sys, types, importlib.util, pathlib
d = pathlib.Path({str(REPO_ROOT / ".hermes" / "plugins" / "planning-with-files")!r})
pkg = types.ModuleType("pwf_hermes")
pkg.__path__ = [str(d)]
sys.modules["pwf_hermes"] = pkg
for name in ("constants", "paths", "hook_state", "planning_files", "hooks"):
    spec = importlib.util.spec_from_file_location("pwf_hermes." + name, d / (name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["pwf_hermes." + name] = mod
    spec.loader.exec_module(mod)
out = sys.modules["pwf_hermes.hooks"].build_user_prompt_context(pathlib.Path("."))
# Write UTF-8 bytes directly: the injected banner carries an em dash, and a
# piped stdout on Windows would otherwise encode it as cp1252.
sys.stdout.buffer.write(out.encode("utf-8"))
"""


@unittest.skipUnless(have_sh(), "sh not available on this platform")
class NoRawWallClockTests(unittest.TestCase):
    """No raw wall-clock time may reach the model on ANY injection route.

    Legacy-root fixture (task_plan.md / progress.md at the fixture root): the
    cursor hook reads only ./task_plan.md and ./progress.md, and the codex hook
    falls back to the root files when no .planning/ dir exists, so this single
    fixture shape exercises all three routes on the same input.

    The plan file deliberately contains no timestamps — the injected plan HEAD
    is not normalized on any route (plan content is user-owned); only the
    progress tail carries machine-written wall-clock times.
    """

    RAW_CLOCK = "T11:02:55"
    RAW_CLOCK_SUBSEC = "T09:16:03"

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="pwf-wallclock-"))
        self.cache_dir = self.tmp / "_xdg_cache"
        self.cache_dir.mkdir()
        self.home_dir = self.tmp / "_home"
        self.home_dir.mkdir()
        self.env = scrubbed_env(
            XDG_CACHE_HOME=str(self.cache_dir),
            HOME=str(self.home_dir),
        )
        (self.tmp / "task_plan.md").write_text(
            "# Legacy Root Plan\nphase 1\n", encoding="utf-8"
        )
        (self.tmp / "progress.md").write_text(PROGRESS_CONTENT, encoding="utf-8")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, argv: list[str]):
        return subprocess.run(
            argv,
            cwd=str(self.tmp),
            text=True,
            encoding="utf-8",
            capture_output=True,
            env=self.env,
            check=False,
        )

    def _assert_normalized(self, stdout: str, route: str) -> None:
        # Vacuous-pass guard: the route must actually have injected the tail.
        self.assertIn(
            "=== recent progress ===",
            stdout,
            f"{route}: expected a progress tail in the injected output",
        )
        self.assertNotIn(
            self.RAW_CLOCK,
            stdout,
            f"{route}: raw wall-clock time leaked into injected output "
            f"(KV-cache buster — every turn gets a different byte stream)",
        )
        self.assertNotIn(
            self.RAW_CLOCK_SUBSEC,
            stdout,
            f"{route}: raw sub-second wall-clock time leaked into injected output",
        )
        self.assertIn(
            "T00:00:00Z",
            stdout,
            f"{route}: expected the normalized epoch-zero form in the tail",
        )

    def test_canonical_inject_plan_normalizes_wall_clock(self) -> None:
        result = self._run(["sh", str(INJECT_PLAN), "--context=userprompt"])
        self.assertEqual(0, result.returncode, result.stderr)
        self._assert_normalized(result.stdout, "scripts/inject-plan.sh")

    def test_cursor_hook_normalizes_wall_clock(self) -> None:
        result = self._run(["sh", str(CURSOR_HOOK)])
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("ACTIVE PLAN", result.stdout)
        self._assert_normalized(result.stdout, ".cursor/hooks/user-prompt-submit.sh")

    def test_codex_hook_normalizes_wall_clock(self) -> None:
        result = self._run(["sh", str(CODEX_HOOK)])
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("ACTIVE PLAN", result.stdout)
        self._assert_normalized(result.stdout, ".codex/hooks/user-prompt-submit.sh")

    def test_hermes_adapter_normalizes_wall_clock(self) -> None:
        # The Hermes plugin builds its injection in Python rather than in shell,
        # so it never received the v2.40 sed pass. Same contract, same fixture.
        # Its package directory name contains a dash, so it cannot be imported
        # by name; load it under a synthetic package instead.
        result = self._run([sys.executable, "-c", _HERMES_PROBE])
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("ACTIVE PLAN", result.stdout)
        self._assert_normalized(result.stdout, ".hermes/plugins/planning-with-files")


if __name__ == "__main__":
    unittest.main()
