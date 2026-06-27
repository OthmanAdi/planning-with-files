"""Regression tests for the PreCompact reminder (v2.38.0, v3 dispatcher).

PreCompact fires on Claude Code's autoCompact and manual /compact. It re-injects
a planning reminder before context compaction. Contract:
  - Declared in the canonical SKILL.md frontmatter with a wildcard matcher so
    both manual and auto triggers fire.
  - The scalar is a thin v3 dispatcher to scripts/inject-plan.sh (build decision
    "hooks become thin dispatchers"); it carries the --context=precompact flag.
  - inject-plan.sh --context=precompact prints a reminder when task_plan.md
    exists, stays silent when absent, and surfaces Plan-SHA256 when an
    attestation is set.

History: this file used to extract the inline PreCompact bash scalar and run it
standalone. v3 reduced the scalar to a dispatcher that exits silently without
CLAUDE_SKILL_DIR, so the behavioral assertions now run inject-plan.sh directly
with CLAUDE_SKILL_DIR set. The contract is unchanged.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_SKILL = REPO_ROOT / "skills" / "planning-with-files" / "SKILL.md"
SKILL_DIR = REPO_ROOT / "skills" / "planning-with-files"
INJECT_PLAN = SKILL_DIR / "scripts" / "inject-plan.sh"


def extract_precompact_scalar(text: str) -> str:
    """Pull the PreCompact command scalar out of SKILL.md frontmatter."""
    in_section = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "PreCompact:":
            in_section = True
            continue
        if in_section and stripped.startswith("command:"):
            m = re.match(r'command:\s*"(.+)"\s*$', stripped)
            if m:
                return m.group(1).replace('\\"', '"')
        if in_section and stripped.endswith(":") and not stripped.startswith("-") and stripped != "hooks:":
            break
    return ""


class PreCompactHookDeclarationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = CANONICAL_SKILL.read_text(encoding="utf-8")

    def test_precompact_is_declared(self) -> None:
        self.assertIn("PreCompact:", self.text, "PreCompact hook missing from canonical SKILL.md")

    def test_precompact_uses_wildcard_matcher(self) -> None:
        # We want both autoCompact and manual /compact to fire the reminder.
        self.assertRegex(
            self.text,
            r"PreCompact:\s*\n\s*-\s*matcher:\s*\"\*\"",
            "PreCompact should match all triggers ('*'), got something stricter",
        )

    def test_precompact_scalar_is_thin_dispatcher(self) -> None:
        # The scalar must dispatch to inject-plan.sh with the precompact context,
        # carry both install fallbacks, and contain no literal '---' (YAML
        # collision class, Discussion #153).
        scalar = extract_precompact_scalar(self.text)
        self.assertTrue(scalar, "Could not extract PreCompact scalar from SKILL.md")
        self.assertIn("${CLAUDE_SKILL_DIR}/scripts/inject-plan.sh", scalar)
        self.assertIn("--context=precompact", scalar)
        self.assertIn(
            "$HOME/.claude/skills/planning-with-files/scripts/inject-plan.sh", scalar
        )
        self.assertNotIn("---", scalar)


@unittest.skipUnless(shutil.which("sh"), "sh not available on this platform")
class PreCompactDispatcherSilentTests(unittest.TestCase):
    """The dispatcher scalar itself must never break compaction."""

    def test_dispatcher_silent_exit_when_script_absent(self) -> None:
        scalar = extract_precompact_scalar(CANONICAL_SKILL.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as fake_home:
            script = Path(tmp) / "_precompact_dispatch.sh"
            script.write_text(scalar, encoding="utf-8")
            env = os.environ.copy()
            env.pop("CLAUDE_SKILL_DIR", None)
            env["HOME"] = fake_home
            result = subprocess.run(
                ["sh", str(script)],
                cwd=tmp,
                text=True,
                encoding="utf-8",
                capture_output=True,
                env=env,
                check=False,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual("", result.stdout.strip())


@unittest.skipUnless(shutil.which("sh"), "sh not available on this platform")
class PreCompactBehaviorTests(unittest.TestCase):
    """Run inject-plan.sh --context=precompact directly (dispatcher target)."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="pwf-precompact-"))
        self.home_dir = self.tmp / "_home"
        self.home_dir.mkdir()
        self.env = os.environ.copy()
        self.env["CLAUDE_SKILL_DIR"] = str(SKILL_DIR)
        self.env["HOME"] = str(self.home_dir)
        self.env["XDG_CACHE_HOME"] = str(self.tmp / "_cache")
        self.env.pop("PLAN_ID", None)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["sh", str(INJECT_PLAN), "--context=precompact"],
            cwd=str(self.tmp),
            text=True,
            encoding="utf-8",
            capture_output=True,
            env=self.env,
            check=False,
        )

    def test_silent_when_no_plan(self) -> None:
        result = self._run()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("", result.stdout.strip(), "PreCompact should be silent without task_plan.md")

    def test_emits_reminder_when_plan_exists(self) -> None:
        (self.tmp / "task_plan.md").write_text("# Plan\n", encoding="utf-8")
        result = self._run()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("[planning-with-files] PreCompact", result.stdout)
        self.assertIn("progress.md", result.stdout, "reminder must mention progress.md")

    def test_emits_plan_sha256_when_legacy_attestation_set(self) -> None:
        (self.tmp / "task_plan.md").write_text("# Plan\n", encoding="utf-8")
        (self.tmp / ".plan-attestation").write_text(
            "abc123def456" + "0" * 52 + "\n", encoding="utf-8"
        )
        result = self._run()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("Plan-SHA256", result.stdout)

    def test_no_sha256_line_when_no_attestation(self) -> None:
        (self.tmp / "task_plan.md").write_text("# Plan\n", encoding="utf-8")
        result = self._run()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertNotIn("Plan-SHA256", result.stdout)


if __name__ == "__main__":
    unittest.main()
