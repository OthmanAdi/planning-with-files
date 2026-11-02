"""scripts/inject-plan.py is a byte-identical twin of the shell hook chain.

The Claude Code plugin answered every lifecycle event through hooks/claude-hook.sh,
resolve-plan-dir.sh and inject-plan.sh, about 130 forks per UserPromptSubmit.
Under Git Bash on Windows a fork costs about 90 ms, so a prompt paid seven to
twelve seconds against the 10 s hook timeout and Claude Code discarded the plan
("UserPromptSubmit hook timed out after 10s"). PreToolUse paid five more seconds
before every tool call. v3.17.0 answers those events in one CPython process,
scripts/inject-plan.py, and keeps the shell chain as the reference
implementation and as the fallback for hosts without Python.

A twin is only worth having while it is provably the same thing. Every test
here runs the reference and the twin over one fixture, each with its own cache
root, and asserts identical stdout bytes: injector contexts, dispatcher events,
notices, refusals, framing digests, truncation flags, the progress-regression
guard across two fires, smart extraction, attestation, v3 modes, session
isolation and nested-root ambiguity. The launcher tests then prove the fast
path is the one that actually runs, and that it falls back to the reference
chain whenever the twin cannot run.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"
SH_INJECT = SCRIPTS / "inject-plan.sh"
PY_INJECT = SCRIPTS / "inject-plan.py"
CLAUDE_HOOK = REPO_ROOT / "hooks" / "claude-hook.sh"
SH = shutil.which("sh")
PY = sys.executable

CONTEXTS = ("userprompt", "pretool", "precompact", "preflight", "validate")
EVENTS = ("session-start", "user-prompt-submit", "pre-tool-use", "post-tool-use", "pre-compact")
SCRUBBED = (
    "PLAN_ID", "PWF_PLAN_ROOT", "PWF_SESSION_ID", "PLANNING_DISABLED",
    "PWF_TRUSTED_PYTHON", "PYTHON_BIN", "PWF_INJECT", "PWF_PLAN_GUARD",
    "PWF_FAST_PATH", "PWF_SESSION_KEY",
)

PHASE_PLAN = (
    "# Task Plan: parity\n\n## Goal\n\nProve the twin.\n\n## Next Step\n\nRun it.\n\n"
    "## Current Phase\n\nPhase 2\n\n## Phases\n\n"
    "### Phase 1: Read\n- [x] read the shell\n- [x] read the tests\n- **Status:** complete\n\n"
    "### Phase 2: Write\n- [x] write the twin\n- [ ] prove it\n- **Status:** in_progress\n\n"
    "### Phase 3: Ship\n- [ ] release\n- **Status:** pending\n\n"
    "## Decisions Made\n\n| Decision | Why |\n|---|---|\n| one | first |\n| two | second |\n"
    "| three | third |\n| four | fourth |\n\n## Errors\n\n| Error | Fix |\n|---|---|\n"
)
PROGRESS = (
    "# Progress\n\n## Session 2026-09-07\n- 2026-09-07T05:46:32Z started\n"
    "- 2026-09-07T06:01:02.250+02:00 measured\n- wrote \"quoted\" and back\\slash\n"
)


def write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, str):
        data = data.encode("utf-8")
    path.write_bytes(data)


def attest(plan: Path, target: Path) -> None:
    target.write_text(hashlib.sha256(plan.read_bytes()).hexdigest(), encoding="ascii")


@unittest.skipUnless(SH, "requires a POSIX sh")
class ParityCase(unittest.TestCase):
    """Fixture plumbing shared by every parity test."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="pwf-parity-")
        self.base = Path(self.tmp.name)
        self.project = self.base / "project"
        self.project.mkdir()
        self.home = self.base / "home"
        self.home.mkdir()
        self.caches = {"sh": self.base / "cache-sh", "py": self.base / "cache-py"}

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def env(self, impl: str, extra: dict | None = None) -> dict:
        env = os.environ.copy()
        for name in SCRUBBED:
            env.pop(name, None)
        env["XDG_CACHE_HOME"] = str(self.caches[impl])
        env["HOME"] = str(self.home)
        env["USERPROFILE"] = str(self.home)
        if extra:
            env.update(extra)
        return env

    def run_inject(self, impl: str, context: str, cwd: Path | None = None,
                   extra: dict | None = None) -> bytes:
        if impl == "sh":
            command = [SH, str(SH_INJECT), "--context=" + context]
        else:
            command = [PY, "-I", "-B", str(PY_INJECT), "--context=" + context]
        result = subprocess.run(
            command, cwd=str(cwd or self.project), env=self.env(impl, extra),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=240, check=False,
        )
        self.assertEqual(0, result.returncode, (impl, context, result.stderr))
        return result.stdout

    def run_event(self, impl: str, event: str, cwd: Path | None = None,
                  extra: dict | None = None) -> bytes:
        env_extra = dict(extra or {})
        if impl == "sh":
            env_extra["PWF_FAST_PATH"] = "0"
            env_extra["CLAUDE_PLUGIN_ROOT"] = str(REPO_ROOT)
            command = [SH, str(CLAUDE_HOOK), event]
        else:
            command = [PY, "-I", "-B", str(PY_INJECT), "--claude-event=" + event]
        result = subprocess.run(
            command, cwd=str(cwd or self.project), env=self.env(impl, env_extra),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=240, check=False,
        )
        self.assertEqual(0, result.returncode, (impl, event, result.stderr))
        return result.stdout

    def assert_parity(self, cwd: Path | None = None, extra: dict | None = None,
                      contexts=CONTEXTS, expect=None, forbid=None) -> dict:
        """Run every context through both implementations; return the sh outputs."""
        outputs = {}
        for context in contexts:
            ref = self.run_inject("sh", context, cwd, extra)
            twin = self.run_inject("py", context, cwd, extra)
            self.assertEqual(ref, twin, "context=%s\n--- sh ---\n%r\n--- py ---\n%r" % (context, ref, twin))
            outputs[context] = ref
        if expect:
            for context, needle in expect.items():
                self.assertIn(needle.encode("utf-8"), outputs[context], context)
        if forbid:
            for context, needle in forbid.items():
                self.assertNotIn(needle.encode("utf-8"), outputs[context], context)
        return outputs

    def assert_event_parity(self, cwd: Path | None = None, extra: dict | None = None,
                            events=EVENTS) -> dict:
        outputs = {}
        for event in events:
            ref = self.run_event("sh", event, cwd, extra)
            twin = self.run_event("py", event, cwd, extra)
            self.assertEqual(ref, twin, "event=%s\n--- sh ---\n%r\n--- py ---\n%r" % (event, ref, twin))
            outputs[event] = ref
        return outputs

    # --- fixture builders ----------------------------------------------------

    def legacy_root(self, plan=PHASE_PLAN, progress=PROGRESS) -> Path:
        plan_path = self.project / "task_plan.md"
        write(plan_path, plan)
        if progress is not None:
            write(self.project / "progress.md", progress)
        return plan_path

    def slug(self, name: str, plan=PHASE_PLAN, progress=PROGRESS, mtime: int | None = None) -> Path:
        directory = self.project / ".planning" / name
        write(directory / "task_plan.md", plan.replace("parity", name) if isinstance(plan, str) else plan)
        if progress is not None:
            write(directory / "progress.md", progress)
        if mtime is not None:
            os.utime(directory, (mtime, mtime))
        return directory


class InjectorParityTests(ParityCase):
    def test_legacy_root_plan_all_contexts(self):
        self.legacy_root()
        out = self.assert_parity(expect={
            "userprompt": "ACTIVE PLAN", "pretool": "kind=plan",
            "precompact": "PreCompact", "preflight": "PWF_PLAN_ELIGIBLE_V1",
            "validate": "PWF_PLAN_ACCEPTED_V1",
        })
        self.assertIn(b"kind=progress", out["userprompt"])
        self.assertIn(b"T00:00:00Z", out["userprompt"])
        self.assertIn(b"T00:00:00+02:00", out["userprompt"])
        self.assertNotIn(b"T05:46:32Z", out["userprompt"])

    def test_no_plan_is_silent_everywhere(self):
        self.assert_parity(forbid={c: "planning-with-files" for c in CONTEXTS})

    def test_long_crlf_plan_and_long_progress_report_truncation(self):
        lines = ["# Task Plan: long\r"] + ["- [x] item %02d\r" % i for i in range(70)]
        self.legacy_root(plan="\n".join(lines) + "\n",
                         progress="\n".join("- line %02d at 2026-01-01T12:00:00Z" % i for i in range(40)) + "\n")
        out = self.assert_parity(expect={"userprompt": "truncated=true", "pretool": "truncated=true"})
        self.assertEqual(2, out["userprompt"].count(b"truncated=true"))

    def test_plan_without_trailing_newline(self):
        self.legacy_root(plan="# Task Plan: bare\n- [ ] one\n- [ ] two", progress="# P\n- x\n")
        # The frame's own newline is the only one between the payload and END.
        self.assert_parity(expect={"userprompt": "- [ ] two\n===END-PWF-DATA kind=plan"})

    @unittest.skipIf(sys.platform == "darwin", "BSD sed appends a newline the GNU reference and the twin do not")
    def test_progress_without_trailing_newline(self):
        self.legacy_root(progress="# P\n- last line has no newline")
        self.assert_parity(expect={"userprompt": "no newline\n===END-PWF-DATA kind=progress"})

    def test_crlf_progress_tail_matches_the_local_sed(self):
        """Git for Windows' sed drops the CR before each LF; GNU and BSD sed keep it.

        The twin mirrors whichever the local reference does, and the frame's
        bytes= and sha256= prove it: a single kept or dropped byte changes both.
        """
        progress = b"l1\r\nl2\r\r\nl3 at 2026-01-01T10:11:12Z\r\nl4 at 2026-01-01T10:11:12.5+02:00\r\n"
        self.legacy_root(progress=progress)
        out = self.assert_parity(contexts=("userprompt",))
        body = out["userprompt"]
        if os.name == "nt":
            self.assertIn(b"l1\nl2\r\nl3 at 2026-01-01T00:00:00Z\nl4 at 2026-01-01T00:00:00+02:00\n", body)
        else:
            self.assertIn(b"l1\r\nl2\r\r\nl3 at 2026-01-01T00:00:00Z\r\nl4 at 2026-01-01T00:00:00+02:00\r\n", body)

    def test_progress_missing_empty_and_symlinked(self):
        self.legacy_root(progress=None)
        self.assert_parity(expect={"userprompt": "kind=progress nonce="})
        write(self.project / "progress.md", b"")
        self.assert_parity(expect={"userprompt": "bytes=0 sha256="})
        outside = self.base / "outside-progress.md"
        write(outside, "OUTSIDE\n")
        (self.project / "progress.md").unlink()
        try:
            (self.project / "progress.md").symlink_to(outside)
        except OSError:
            self.skipTest("symlinks unavailable")
        self.assert_parity(forbid={"userprompt": "ACTIVE PLAN"})

    def test_non_utf8_and_control_bytes_pass_through_the_frame(self):
        self.legacy_root(plan=b"# Task Plan: bytes\n\xff\xfe raw \x01 ctrl \x00 nul\n- [x] ok\n",
                         progress=b"- \xe2\x9c\x93 done \x7f\n")
        out = self.assert_parity()
        self.assertIn(b"\xff\xfe raw \x01 ctrl \x00 nul", out["userprompt"])
        self.assertIn(b"\xe2\x9c\x93 done \x7f", out["userprompt"])

    def test_active_plan_pointer_with_padding_selects_the_slug(self):
        self.slug("2026-09-01-alpha", mtime=1_700_000_000)
        write(self.project / ".planning" / ".active_plan", "  2026-09-01-alpha \r\n")
        self.assert_parity(expect={"userprompt": "Task Plan: 2026-09-01-alpha"},
                           forbid={"userprompt": "2026-09-03-beta"})

    def test_active_plan_with_nul_bytes_still_names_its_plan(self):
        """Command substitution drops NUL bytes, so the reference reads a
        UTF-16LE pointer without a BOM as its ASCII slug; a UTF-16 BOM is not
        whitespace and still invalidates the pointer."""
        self.slug("2026-09-01-alpha", mtime=1_700_000_000)
        for pointer in (b"2026-09-01-alpha\x00\n", "2026-09-01-alpha\n".encode("utf-16-le")):
            write(self.project / ".planning" / ".active_plan", pointer)
            self.assert_parity(expect={"userprompt": "Task Plan: 2026-09-01-alpha"},
                               forbid={"userprompt": "2026-09-03-beta"})
            self.assert_event_parity(events=("session-start", "post-tool-use"))
        write(self.project / ".planning" / ".active_plan", "2026-09-01-alpha\n".encode("utf-16"))
        self.assert_parity(expect={"userprompt": "Task Plan: 2026-09-01-alpha"})

    def test_bom_pointer_is_rejected_and_single_live_plan_wins(self):
        self.slug("2026-09-03-beta", mtime=1_700_000_100)
        write(self.project / ".planning" / ".active_plan", b"\xef\xbb\xbf2026-09-01-alpha\n")
        self.assert_parity(expect={"userprompt": "Task Plan: 2026-09-03-beta"})

    def test_newest_scan_skips_invalid_slugs_and_planless_dirs(self):
        self.slug("2026-09-01-alpha", mtime=1_700_000_000)
        self.slug("2026-09-02-newer-but-planless", plan=PHASE_PLAN, mtime=1_700_000_300)
        (self.project / ".planning" / "2026-09-02-newer-but-planless" / "task_plan.md").unlink()
        os.utime(self.project / ".planning" / "2026-09-02-newer-but-planless", (1_700_000_300, 1_700_000_300))
        bad = self.project / ".planning" / "bad slug"
        write(bad / "task_plan.md", "# bad\n")
        os.utime(bad, (1_700_000_400, 1_700_000_400))
        hidden = self.project / ".planning" / ".hidden"
        write(hidden / "task_plan.md", "# hidden\n")
        os.utime(hidden, (1_700_000_500, 1_700_000_500))
        self.assert_parity(expect={"userprompt": "Task Plan: 2026-09-01-alpha"})

    def test_plan_id_binding_valid_and_rejected(self):
        self.slug("plan-a")
        self.slug("plan-b")
        self.legacy_root()
        self.assert_parity(extra={"PLAN_ID": "plan-b"}, expect={"userprompt": "Task Plan: plan-b"})
        for ghost in ("plan-ghost", "../plan-a", ".hidden", "with space"):
            self.assert_parity(extra={"PLAN_ID": ghost},
                               expect={"userprompt": "PLAN_ID does not name a plan directory"},
                               forbid={"pretool": "PLAN_ID", "preflight": "PWF_PLAN", "validate": "PWF_PLAN"})

    def test_plan_root_pin_valid_relative_and_missing(self):
        nested = self.project / "nested"
        write(nested / ".planning" / "inner" / "task_plan.md", "# Task Plan: inner\n- [ ] x\n")
        write(nested / ".planning" / "inner" / "progress.md", "- inner progress\n")
        self.legacy_root()
        self.assert_parity(extra={"PWF_PLAN_ROOT": str(nested)}, expect={"userprompt": "Task Plan: inner"})
        self.assert_parity(extra={"PWF_PLAN_ROOT": "nested"},
                           expect={"userprompt": "not a supported absolute local directory",
                                   "pretool": "not a supported absolute local directory"},
                           forbid={"preflight": "not a supported"})
        self.assert_parity(extra={"PWF_PLAN_ROOT": str(self.base / "does-not-exist")},
                           expect={"userprompt": "not a supported absolute local directory"})

    def test_nested_ambiguity_lists_three_sorted_and_ignores_dead_pointers(self):
        # Lowercase names on purpose: the shell lists nested projects in glob
        # (locale collation) order and the twin in code-point order, which
        # only agree when case and punctuation cannot reorder them. That is
        # an accepted difference documented in the twin's header.
        self.legacy_root()
        for name in ("delta", "alpha", "charlie", "bravo"):
            write(self.project / name / ".planning" / "p" / "task_plan.md", "# nested\n")
        write(self.project / "dead" / ".planning" / ".active_plan", "gone\n")
        (self.project / "empty" / ".planning").mkdir(parents=True)
        out = self.assert_parity(expect={"userprompt": "Ambiguous plan"},
                                 forbid={"pretool": "Ambiguous", "validate": "PWF_PLAN_ACCEPTED_V1"})
        self.assertIn(b"(alpha, bravo, charlie)", out["userprompt"])
        self.assertNotIn(b"delta", out["userprompt"])
        self.assertIn(b"PWF_PLAN_ELIGIBLE_V1", out["preflight"])

    def test_nested_planning_without_live_plan_does_not_conflict(self):
        self.legacy_root()
        write(self.project / "child" / ".planning" / ".active_plan", "x\n")
        (self.project / "child" / ".planning" / "x").mkdir()
        self.assert_parity(expect={"userprompt": "ACTIVE PLAN"})

    def test_session_isolation_notices_and_attachment(self):
        self.slug("plan-a")
        write(self.project / ".planning" / ".active_plan", "plan-a\n")
        sessions = self.project / ".planning" / "sessions"
        sessions.mkdir()
        self.assert_parity(expect={"userprompt": "Session isolation is armed"},
                           forbid={"pretool": "isolation"})
        self.assert_parity(extra={"PWF_SESSION_ID": "nobody"},
                           expect={"userprompt": "Session isolation is armed"})
        write(sessions / "legacy-session.attached", "")
        self.assert_parity(extra={"PWF_SESSION_ID": "legacy-session"},
                           expect={"userprompt": "Task Plan: plan-a"})
        project_norm = os.path.normcase(os.path.realpath(os.path.abspath(str(self.project)))).replace("\\", "/")
        digest = hashlib.sha256()
        for value in ("portable", project_norm, "digest/session"):
            encoded = value.encode("utf-8", "surrogatepass")
            digest.update(len(encoded).to_bytes(8, "big"))
            digest.update(encoded)
        write(sessions / (digest.hexdigest() + ".attached"), "")
        self.assert_parity(extra={"PWF_SESSION_ID": "digest/session"},
                           expect={"userprompt": "Task Plan: plan-a"})
        self.slug("plan-b")
        self.assert_parity(extra={"PWF_SESSION_ID": "legacy-session"},
                           expect={"userprompt": "Multiple plans are available"})
        self.assert_parity(extra={"PWF_SESSION_ID": "legacy-session", "PLAN_ID": "plan-b"},
                           expect={"userprompt": "Task Plan: plan-b"})

    def test_ambiguity_notices_point_at_plan_archiving(self):
        # #355: an agent cannot set PLAN_ID for the hook process, but it can
        # archive finished plans until one remains, so both notices name that.
        hint = b"nothing injected. Finished plans can be archived with set-active-plan --archive <slug>.\n"
        self.slug("plan-a")
        self.slug("plan-b")
        unarmed = self.assert_parity(contexts=("userprompt",))["userprompt"]
        self.assertTrue(unarmed.endswith(hint), unarmed)
        sessions = self.project / ".planning" / "sessions"
        sessions.mkdir()
        write(sessions / "legacy-session.attached", "")
        armed = self.assert_parity(contexts=("userprompt",), extra={"PWF_SESSION_ID": "legacy-session"},
                                   expect={"userprompt": "while session isolation is armed"})["userprompt"]
        self.assertTrue(armed.endswith(hint), armed)

    def test_linked_plan_directory_never_counts_as_a_second_plan(self):
        # #270: a symlinked or junctioned plan directory is not selectable, so
        # the several-plans counter skips it on both implementations.
        self.slug("plan-a")
        write(self.project / ".planning" / ".active_plan", "plan-a\n")
        target = self.project / "linked-target"
        write(target / "task_plan.md", PHASE_PLAN.replace("parity", "linked"))
        link = self.project / ".planning" / "plan-b"
        if os.name == "nt":
            made = subprocess.run(["cmd", "/d", "/c", "mklink", "/J", str(link), str(target)],
                                  capture_output=True, text=True, check=False)
            if made.returncode != 0:
                self.skipTest("junction creation unavailable: " + made.stderr.strip())
        else:
            try:
                link.symlink_to(target, target_is_directory=True)
            except OSError:
                self.skipTest("symlinks unavailable")
        self.assert_parity(expect={"userprompt": "Task Plan: plan-a"},
                           forbid={"userprompt": "Multiple plans are available"})
        # a real second plan still trips the counter on both sides
        self.slug("plan-c")
        self.assert_parity(expect={"userprompt": "Multiple plans are available"})

    def test_attestation_ok_padded_and_tampered(self):
        plan = self.legacy_root()
        attest(plan, self.project / ".plan-attestation")
        digest = (self.project / ".plan-attestation").read_text()
        out = self.assert_parity(expect={"userprompt": "Plan-SHA256: " + digest,
                                         "precompact": "Plan-SHA256 at compaction: " + digest})
        self.assertIn(b"ACTIVE PLAN", out["userprompt"])
        (self.project / ".plan-attestation").write_text("  " + digest + "\r\n\n", encoding="ascii")
        self.assert_parity(expect={"userprompt": "Plan-SHA256: " + digest})
        plan.write_text(PHASE_PLAN + "\n- tampered\n", encoding="utf-8")
        out = self.assert_parity(expect={"userprompt": "PLAN TAMPERED", "pretool": "PLAN TAMPERED"})
        self.assertIn(("expected=" + digest).encode(), out["userprompt"])
        self.assertIn(b"actual=  ", out["userprompt"])
        self.assertNotIn(b"tampered\n", out["pretool"])

    def test_oversized_attestation_refuses(self):
        self.legacy_root()
        write(self.project / ".plan-attestation", "a" * 129)
        self.assert_parity(forbid={"userprompt": "ACTIVE PLAN", "precompact": "PreCompact"})

    def test_v3_modes_unattested_attested_and_ledgers(self):
        plan = self.legacy_root()
        write(self.project / ".mode", "autonomous\n")
        self.assert_parity(expect={"userprompt": "requires attested plan"},
                           forbid={"pretool": "planning"})
        attest(plan, self.project / ".plan-attestation")
        write(self.project / "ledger-worker.jsonl",
              '{"tick":1,"event":"start"}\n{"tick":2,"event":"phase_complete"}\n')
        write(self.project / "ledger-reviewer.jsonl", '{"tick":1,"event":"review"}\n')
        out = self.assert_parity(expect={"userprompt": "=== RUN LEDGER ==="})
        self.assertIn(b"entries: 3", out["userprompt"])
        self.assertIn(b"agent reviewer: review", out["userprompt"])
        self.assertIn(b"agent worker: phase_complete", out["userprompt"])
        self.assertEqual(b"", out["pretool"])
        write(self.project / ".mode", "autonomous gate\n")
        self.assert_parity(expect={"userprompt": "phases: 1/3 complete"})
        write(self.project / "ledger-bad name.jsonl", '{"tick":1}\n')
        self.assert_parity(forbid={"userprompt": "ACTIVE PLAN"})

    def test_root_mode_is_a_floor_for_slug_plans(self):
        slug = self.slug("plan-a")
        write(self.project / ".mode", "autonomous\n")
        write(self.project / ".planning" / ".active_plan", "plan-a\n")
        self.assert_parity(expect={"userprompt": "requires attested plan"})
        attest(slug / "task_plan.md", slug / ".attestation")
        self.assert_parity(expect={"userprompt": "=== RUN LEDGER ==="})
        write(slug / ".mode", "plan-guard-off\n")
        self.assert_parity(expect={"userprompt": "=== RUN LEDGER ==="})

    def test_smart_extraction_phase_plan_headingless_and_mode_token(self):
        self.legacy_root()
        out = self.assert_parity(extra={"PWF_INJECT": "smart"}, expect={"userprompt": "phases: 1/3 complete"})
        body = out["userprompt"]
        self.assertIn(b"### Phase 2: Write", body)
        self.assertNotIn(b"### Phase 1: Read", body)
        self.assertIn(b"## Decisions Made (last 3)", body)
        self.assertIn(b"| two | second |", body)
        self.assertNotIn(b"| one | first |", body)
        self.assertIn(b"truncated=true", body)
        write(self.project / ".mode", "inject-smart\n")
        self.assert_parity(expect={"userprompt": "phases: 1/3 complete", "pretool": "phases: 1/3 complete"})
        (self.project / ".mode").unlink()
        self.legacy_root(plan="# No phases here\n- [ ] just a list\n")
        self.assert_parity(extra={"PWF_INJECT": "smart"}, expect={"userprompt": "- [ ] just a list"},
                           forbid={"userprompt": "phases:"})

    def test_smart_extraction_with_no_completed_phase_prints_the_awk_quirk(self):
        """awk prints a counter that was never incremented as the empty string,
        so a brand-new plan reads "phases: /2 complete" on both routes."""
        plan = ("# Task Plan: fresh\n\n## Goal\n\nStart.\n\n## Phases\n\n"
                "### Phase 1: First\n- [ ] begin\n- **Status:** in_progress\n\n"
                "### Phase 2: Second\n- [ ] later\n- **Status:** pending\n")
        self.legacy_root(plan=plan)
        out = self.assert_parity(extra={"PWF_INJECT": "smart"})
        self.assertIn(b"phases: /2 complete\n", out["userprompt"])
        self.assertIn(b"phases: /2 complete\n", out["pretool"])
        self.assertIn(b"### Phase 1: First", out["pretool"])

    def test_smart_extraction_crlf_and_inline_status_markers(self):
        plan = ("# Title\r\n## Goal\r\nG\r\n## Phases\r\n### Phase 1\r\n[complete]\r\n"
                "### Phase 2\r\n[in_progress]\r\n### Phase 3\r\n[in_progress]\r\n")
        self.legacy_root(plan=plan)
        out = self.assert_parity(extra={"PWF_INJECT": "smart"}, expect={"userprompt": "phases: 1/3 complete"})
        self.assertIn(b"### Phase 2\n[in_progress]\n", out["userprompt"])
        self.assertNotIn(b"### Phase 3", out["userprompt"])

    def test_large_plan_truncates_and_oversized_plan_refuses(self):
        self.legacy_root(plan=b"# Task Plan: big\n" + b"X" * 70_000 + b"\n")
        out = self.assert_parity(expect={"userprompt": "bytes=65536", "pretool": "bytes=65536"})
        self.assertIn(b"truncated=true", out["pretool"])
        self.legacy_root(plan=b"# Task Plan: huge\n" + b"Y" * 4_194_305 + b"\n")
        self.assert_parity(forbid={"userprompt": "ACTIVE PLAN", "pretool": "kind=plan"},
                           expect={"preflight": "PWF_PLAN_ELIGIBLE_V1"})

    def test_symlinked_plan_is_refused(self):
        outside = self.base / "outside-plan.md"
        write(outside, "# OUTSIDE\n")
        try:
            (self.project / "task_plan.md").symlink_to(outside)
        except OSError:
            self.skipTest("symlinks unavailable")
        write(self.project / "progress.md", "- p\n")
        self.assert_parity(forbid={c: "OUTSIDE" for c in CONTEXTS})

    def test_progress_guard_fires_identically_on_the_second_fire(self):
        plan = self.legacy_root()
        first = self.assert_parity(contexts=("userprompt",))
        self.assertNotIn(b"PLAN REGRESSED", first["userprompt"])
        plan.write_text(PHASE_PLAN.replace("- [x] read the tests", "- [ ] read the tests")
                        .replace("- **Status:** complete", "- **Status:** pending"), encoding="utf-8")
        second = self.assert_parity(contexts=("userprompt", "pretool"))
        self.assertIn(b"PLAN REGRESSED: task_plan.md lost 1 checked item(s) and 1 completed phase(s)",
                      second["userprompt"])
        self.assertNotIn(b"REGRESSED", second["pretool"])
        third = self.assert_parity(contexts=("userprompt",))
        self.assertNotIn(b"REGRESSED", third["userprompt"])

    def test_progress_guard_off_switches(self):
        plan = self.legacy_root()
        self.assert_parity(contexts=("userprompt",), extra={"PWF_PLAN_GUARD": "0"})
        plan.write_text("# Task Plan: parity\n- [ ] nothing checked\n", encoding="utf-8")
        self.assert_parity(contexts=("userprompt",), extra={"PWF_PLAN_GUARD": "0"},
                           forbid={"userprompt": "REGRESSED"})
        write(self.project / ".mode", "plan-guard-off\n")
        self.legacy_root()
        self.assert_parity(contexts=("userprompt",))
        plan.write_text("# Task Plan: parity\n- [ ] nothing checked\n", encoding="utf-8")
        self.assert_parity(contexts=("userprompt",), forbid={"userprompt": "REGRESSED"})

    def test_planning_disabled_silences_everything(self):
        self.legacy_root()
        self.assert_parity(extra={"PLANNING_DISABLED": "1"}, forbid={c: "planning" for c in CONTEXTS})

    def test_unknown_context_takes_the_userprompt_shape_without_notices(self):
        self.legacy_root()
        self.assert_parity(contexts=("foo",), expect={"foo": "ACTIVE PLAN"})
        self.assert_parity(contexts=("foo",), extra={"PLAN_ID": "ghost"}, forbid={"foo": "PLAN_ID"})

    def test_project_modules_cannot_shadow_the_standard_library(self):
        """Both routes run their Python with the project directory off sys.path.

        Before v3.17.0 the shell chain ran `python -` heredocs, which put the
        current directory first on sys.path: a repository carrying its own
        secrets.py, hashlib.py or ctypes.py had that file imported by the hook
        on every prompt. The planted modules below record any import; neither
        implementation may run them, and both must still inject the plan.
        """
        self.legacy_root()
        for name in ("secrets", "hashlib", "ctypes", "stat", "re", "json"):
            write(self.project / (name + ".py"),
                  "open('PLANTED_" + name + "', 'w').close()\nraise SystemExit(99)\n")
        self.assert_parity(expect={"userprompt": "ACTIVE PLAN", "pretool": "kind=plan"})
        planted = sorted(p.name for p in self.project.glob("PLANTED_*"))
        self.assertEqual([], planted, "a hook imported a module from the project directory")


class DispatcherParityTests(ParityCase):
    def test_all_events_on_a_legacy_plan_with_json_hostile_bytes(self):
        # The emoji is outside the BMP: gawk in a UTF-8 locale on Windows used
        # to walk it as two UTF-16 units and emit a lone surrogate. The
        # dispatcher now runs awk byte-wise, so both routes emit valid UTF-8.
        self.legacy_root(plan='# Task Plan: "quoted" back\\slash\ttab\r\n- [x] c:\\path\\ok\x01\n'
                              '- [ ] \x00nul\n- [ ] caf\u00e9 \u6f22 \U0001f642\n',
                         progress='- "p"\\q\r\n')
        out = self.assert_event_parity()
        self.assertIn("caf\u00e9 \u6f22 \U0001f642".encode("utf-8"), out["user-prompt-submit"])
        json.loads(out["user-prompt-submit"])
        for event in EVENTS:
            self.assertTrue(out[event].endswith(b"}\n"), event)
        self.assertIn(b'"hookEventName":"UserPromptSubmit"', out["user-prompt-submit"])
        self.assertIn(b'"hookEventName":"SessionStart"', out["session-start"])
        self.assertIn(b'"systemMessage":"[planning-with-files] PreCompact', out["pre-compact"])
        self.assertIn(b"Update progress.md", out["post-tool-use"])
        for impl in ("sh", "py"):
            self.assertEqual(b"", self.run_event(impl, "post-tool-use"))
            self.run_event(impl, "user-prompt-submit")
            self.assertIn(b"Update progress.md", self.run_event(impl, "post-tool-use"))
            self.assertEqual(b"", self.run_event(impl, "post-tool-use"))
            self.run_event(impl, "session-start")
            self.assertIn(b"Update progress.md", self.run_event(impl, "post-tool-use"))

    def test_events_on_a_slug_plan_with_session_ids(self):
        self.slug("plan-a")
        write(self.project / ".planning" / ".active_plan", "plan-a\n")
        self.assert_event_parity(extra={"PWF_SESSION_ID": "alpha"})
        for impl in ("sh", "py"):
            self.assertEqual(b"", self.run_event(impl, "post-tool-use", extra={"PWF_SESSION_ID": "alpha"}))
            self.assertIn(b"Update progress.md", self.run_event(impl, "post-tool-use", extra={"PWF_SESSION_ID": "beta"}))

    def test_events_with_no_plan_rejected_pin_and_ambiguity(self):
        out = self.assert_event_parity()
        self.assertEqual({e: b"" for e in EVENTS}, out)
        self.legacy_root()
        self.slug("real")
        out = self.assert_event_parity(extra={"PLAN_ID": "ghost"})
        self.assertEqual(b"", out["post-tool-use"])
        self.assertEqual(b"", out["session-start"])
        self.assertIn(b"PLAN_ID does not name", out["user-prompt-submit"])
        self.assertEqual(b"", out["pre-tool-use"])
        out = self.assert_event_parity(extra={"PWF_PLAN_ROOT": "relative"})
        self.assertEqual(b"", out["session-start"])
        self.assertIn(b"not a supported absolute", out["user-prompt-submit"])
        write(self.project / "child" / ".planning" / "p" / "task_plan.md", "# c\n")
        out = self.assert_event_parity()
        self.assertIn(b"Ambiguous plan", out["user-prompt-submit"])
        self.assertEqual(b"", out["pre-tool-use"])
        self.assertIn(b"Update progress.md", out["post-tool-use"])

    def test_broken_cache_root_behaves_identically(self):
        self.legacy_root()
        blocker = self.base / "not-a-dir"
        blocker.write_text("file", encoding="utf-8")
        for impl in ("sh", "py"):
            self.caches[impl] = blocker
        out = self.assert_event_parity()
        self.assertEqual(b"", out["user-prompt-submit"])
        self.assertIn(b"Update progress.md", out["post-tool-use"])
        self.assertIn(b"Update progress.md", self.run_event("py", "post-tool-use"))
        self.assertIn(b"Update progress.md", self.run_event("sh", "post-tool-use"))


@unittest.skipUnless(SH, "requires a POSIX sh")
class LauncherTests(unittest.TestCase):
    """hooks/claude-hook.sh takes the fast path when it can and falls back when it cannot."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="pwf-launcher-")
        self.base = Path(self.tmp.name)
        self.plugin = self.base / "plugin cache with spaces"
        shutil.copytree(REPO_ROOT / "hooks", self.plugin / "hooks")
        shutil.copytree(REPO_ROOT / "scripts", self.plugin / "scripts",
                        ignore=shutil.ignore_patterns("__pycache__"))
        self.project = self.base / "project"
        self.project.mkdir()
        write(self.project / "task_plan.md", PHASE_PLAN)
        write(self.project / "progress.md", PROGRESS)
        self.env = os.environ.copy()
        for name in SCRUBBED:
            self.env.pop(name, None)
        self.env.update({
            "CLAUDE_PLUGIN_ROOT": str(self.plugin),
            "HOME": str(self.base / "home"),
            "USERPROFILE": str(self.base / "home"),
            "XDG_CACHE_HOME": str(self.base / "cache"),
            "PATH": os.pathsep.join([str(Path(PY).parent), self.env.get("PATH", "")]),
        })

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def run_hook(self, event: str, cwd: Path | None = None, **extra: str) -> subprocess.CompletedProcess:
        env = dict(self.env)
        env.update(extra)
        return subprocess.run(
            [SH, str(self.plugin / "hooks" / "claude-hook.sh"), event],
            cwd=str(cwd or self.project), env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=240, check=False,
        )

    def test_plan_less_directory_answers_nothing_and_starts_no_interpreter(self):
        """No task_plan.md, no .planning, no selector: the reference chain
        answers with nothing after about ten forks; the launcher answers with
        nothing before any fork, and never starts the twin."""
        write(self.plugin / "scripts" / "inject-plan.py",
              "open('TWIN_RAN', 'w').close()\nprint('SHOULD NOT PRINT')\n")
        empty = self.base / "empty project"
        empty.mkdir()
        for event in EVENTS:
            result = self.run_hook(event, cwd=empty)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(b"", result.stdout, event)
            reference = self.run_hook(event, cwd=empty, PWF_FAST_PATH="0")
            self.assertEqual(b"", reference.stdout, event)
        self.assertFalse((empty / "TWIN_RAN").exists(), "the twin ran in a plan-less directory")

    def test_selector_in_a_plan_less_directory_still_gets_its_notice(self):
        empty = self.base / "empty project"
        empty.mkdir()
        for extra in ({"PLAN_ID": "ghost"}, {"PWF_PLAN_ROOT": "relative"}):
            fast = self.run_hook("user-prompt-submit", cwd=empty, **extra)
            reference = self.run_hook("user-prompt-submit", cwd=empty, PWF_FAST_PATH="0", **extra)
            self.assertEqual(0, fast.returncode, fast.stderr)
            self.assertEqual(reference.stdout, fast.stdout, extra)
            self.assertIn(b"nothing injected", fast.stdout, extra)

    def test_both_routes_share_one_cache_slot_per_plan(self):
        """A fallback fire and a fast-path fire on the same plan must land in
        the same turn-marker slot and the same progress-guard slot, otherwise
        the once-per-turn nudge (#239) would fire twice and the regression
        guard (#217) would lose its baseline on every switch."""
        cache = self.base / "shared cache"
        self.run_hook("user-prompt-submit", PWF_FAST_PATH="0", XDG_CACHE_HOME=str(cache))
        self.run_hook("user-prompt-submit", XDG_CACHE_HOME=str(cache))
        slots = sorted(p.name for p in (cache / "pwf-prog").glob("*.prog"))
        self.assertEqual(1, len(slots), slots)

        self.assertIn(b"Update progress.md", self.run_hook("post-tool-use", XDG_CACHE_HOME=str(cache)).stdout)
        self.assertEqual(b"", self.run_hook("post-tool-use", PWF_FAST_PATH="0", XDG_CACHE_HOME=str(cache)).stdout)
        self.run_hook("user-prompt-submit", PWF_FAST_PATH="0", XDG_CACHE_HOME=str(cache))
        self.assertIn(b"Update progress.md",
                      self.run_hook("post-tool-use", PWF_FAST_PATH="0", XDG_CACHE_HOME=str(cache)).stdout)
        self.assertEqual(b"", self.run_hook("post-tool-use", XDG_CACHE_HOME=str(cache)).stdout)
        markers = sorted(p.name for p in (cache / "pwf-turn").glob("*"))
        self.assertEqual(1, len(markers), markers)

    def test_fast_path_is_taken_when_python_is_on_path(self):
        write(self.plugin / "scripts" / "inject-plan.py",
              "import sys\nsys.stdout.write('{\"fast\":\"' + sys.argv[1] + '\"}\\n')\n")
        for event in EVENTS:
            result = self.run_hook(event)
            self.assertEqual(0, result.returncode, result.stderr)
            # The stub writes through text-mode stdout, which Windows ends in CRLF.
            self.assertEqual('{"fast":"--claude-event=%s"}\n' % event,
                             result.stdout.replace(b"\r\n", b"\n").decode())

    def test_stop_never_takes_the_fast_path(self):
        write(self.plugin / "scripts" / "inject-plan.py", "raise SystemExit(0)\n")
        write(self.plugin / "scripts" / "gate-stop.sh", "#!/bin/sh\ncat\n")
        original = '{"stop_hook_active":true}'
        result = subprocess.run(
            [SH, str(self.plugin / "hooks" / "claude-hook.sh"), "stop"],
            cwd=str(self.project), env=self.env, input=original.encode(),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120, check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        # The dispatcher wraps a non-blocking gate answer as systemMessage; the
        # payload inside must be the untouched stdin the stub echoed back.
        self.assertEqual(original, json.loads(result.stdout)["systemMessage"])

    def test_fast_path_output_equals_reference_output(self):
        for event in EVENTS:
            reference = self.run_hook(event, PWF_FAST_PATH="0", XDG_CACHE_HOME=str(self.base / "c-ref"))
            fast = self.run_hook(event, XDG_CACHE_HOME=str(self.base / "c-fast"))
            self.assertEqual(0, reference.returncode, reference.stderr)
            self.assertEqual(0, fast.returncode, fast.stderr)
            self.assertEqual(reference.stdout, fast.stdout, event)
            self.assertIn(b"planning-with-files", fast.stdout)

    def test_twin_that_cannot_run_falls_back_to_the_reference_chain(self):
        reference = self.run_hook("user-prompt-submit", PWF_FAST_PATH="0",
                                  XDG_CACHE_HOME=str(self.base / "c-ref")).stdout
        self.assertIn(b"ACTIVE PLAN", reference)
        # The twin's contract is write-once: nothing reaches stdout before the
        # answer is complete, so a failing twin leaves stdout empty and the
        # reference chain's answer is the whole answer. stderr is free.
        for body in (
            "import sys\nsys.stderr.write('could not run')\nsys.exit(3)\n",
            "print 'python 2 syntax'\n",                            # SyntaxError, exit 1
            "import module_that_does_not_exist\n",                  # ImportError, exit 1
        ):
            write(self.plugin / "scripts" / "inject-plan.py", body)
            result = self.run_hook("user-prompt-submit", XDG_CACHE_HOME=str(self.base / "c-fallback"))
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(reference, result.stdout, body)

    def test_missing_twin_uses_the_reference_chain(self):
        (self.plugin / "scripts" / "inject-plan.py").unlink()
        result = self.run_hook("user-prompt-submit")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn(b"ACTIVE PLAN", result.stdout)

    def test_windowsapps_alias_and_relative_path_entries_are_never_used(self):
        stub_dir = self.base / "Microsoft" / "WindowsApps"
        stub_dir.mkdir(parents=True)
        for name in ("python3", "python"):
            write(stub_dir / name, "#!/bin/sh\necho STUB_RAN\nexit 0\n")
            (stub_dir / name).chmod(0o755)
        relative_dir = self.base / "rel"
        relative_dir.mkdir()
        write(relative_dir / "python3", "#!/bin/sh\necho REL_RAN\nexit 0\n")
        (relative_dir / "python3").chmod(0o755)
        write(self.plugin / "scripts" / "inject-plan.py", "print('REAL_TWIN')\n")
        path = os.pathsep.join([str(stub_dir), "rel", str(Path(PY).parent), self.env["PATH"]])
        result = self.run_hook("user-prompt-submit", PATH=path)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(b"REAL_TWIN\n", result.stdout.replace(b"\r\n", b"\n"))


if __name__ == "__main__":
    unittest.main()
