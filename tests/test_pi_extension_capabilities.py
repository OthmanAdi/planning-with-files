"""Behavioral contract tests for the Pi planning-with-files extension source.

These tests validate that the extension source covers Claude-parity hooks,
DeepSeek cache-safe mode, and loop guard safety constraints.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
EXT_ROOT = REPO_ROOT / ".pi" / "skills" / "planning-with-files" / "extensions" / "planning-with-files"
INDEX_TS = EXT_ROOT / "index.ts"
RUNTIME_TS = EXT_ROOT / "runtime.ts"
PLAN_TS = EXT_ROOT / "plan.ts"
CONSTANTS_TS = EXT_ROOT / "constants.ts"


class PiExtensionCapabilitiesTests(unittest.TestCase):
    def _read(self, path: Path) -> str:
        self.assertTrue(path.exists(), f"missing required source file: {path}")
        return path.read_text(encoding="utf-8")

    def test_required_source_files_exist(self) -> None:
        for path in (INDEX_TS, RUNTIME_TS, PLAN_TS, CONSTANTS_TS):
            self.assertTrue(path.exists(), f"missing required source file: {path}")

    def test_mode_union_contains_auto_parity_cache_safe_notify(self) -> None:
        text = self._read(RUNTIME_TS)
        self.assertRegex(
            text,
            r'type\s+HookMode\s*=\s*"auto"\s*\|\s*"parity"\s*\|\s*"cache-safe"\s*\|\s*"notify"',
        )

    def test_registers_required_hook_events(self) -> None:
        text = self._read(RUNTIME_TS)
        required_events = [
            "session_start",
            "before_agent_start",
            "tool_call",
            "tool_result",
            "agent_end",
            "session_before_compact",
            "input",
        ]
        for event_name in required_events:
            self.assertIn(f'pi.on("{event_name}"', text)

    def test_auto_continue_limit_is_three(self) -> None:
        text = self._read(CONSTANTS_TS)
        self.assertRegex(text, r"AUTO_CONTINUE_LIMIT\s*=\s*3")

    def test_plan_execute_command_is_registered(self) -> None:
        text = self._read(RUNTIME_TS)
        self.assertIn('pi.registerCommand("plan-execute"', text)

    def test_tampered_blocking_message_exists(self) -> None:
        text = self._read(CONSTANTS_TS)
        self.assertIn("PLAN TAMPERED", text)

    def test_plan_resolution_keeps_plan_id_active_plan_and_newest_fallback(self) -> None:
        text = self._read(PLAN_TS)
        self.assertIn("process.env.PLAN_ID", text)
        self.assertIn(".active_plan", text)
        self.assertTrue(
            re.search(r"resolveNewestPlanDir", text),
            "plan resolver must include newest plan directory fallback",
        )

    def test_dangerous_bash_uses_word_boundary_regex(self) -> None:
        # v2.40: substring matching produced false positives on every benign
        # `git push origin <branch>`. The runtime must now use a regex array
        # so only destructive variants (--force, --mirror, rm -rf, sudo,
        # chmod 777, git reset --hard, git clean -fd, fork bomb, dd to disk)
        # trigger the warning.
        text = self._read(RUNTIME_TS)
        self.assertIn(
            "DANGEROUS_BASH_PATTERNS",
            text,
            "runtime must define DANGEROUS_BASH_PATTERNS regex array",
        )
        # Substring-match shape must NOT be present. The v2.39.0 dangerPatterns
        # list with a raw `"git push"` would fire on every benign push.
        self.assertNotIn(
            'dangerPatterns =',
            text,
            "v2.39.0 dangerPatterns substring list still present; replace with "
            "DANGEROUS_BASH_PATTERNS regex array",
        )
        self.assertNotIn(
            '"git push",',
            text,
            "raw substring 'git push' inside the danger list would false-positive "
            "on benign pushes; use the --force/--mirror regex variant instead",
        )
        # Each required pattern, as literal substring of the TS source. These
        # are stable to YAML/JS escaping: they appear verbatim in the file.
        required_substrings = [
            r"\brm\s+-[a-z]*r",                  # rm -rf, rm -fr, rm -Rf
            r"\bsudo\b",                         # sudo
            r"\bchmod\s+(0?777",                 # chmod 777 / chmod 0777
            r"a\+rwx",                           # chmod a+rwx
            r"\bgit\s+push\s+.*(--force",        # forced push
            r"--mirror",                         # mirror push
            r"\bgit\s+reset\s+--hard\b",         # git reset --hard
            r"\bgit\s+clean\s+-",                # git clean -fd family
            r"\bdd\s+.*of=",                     # dd to a raw device
        ]
        missing = [s for s in required_substrings if s not in text]
        self.assertFalse(
            missing,
            "runtime missing required dangerous-command patterns: "
            + ", ".join(missing),
        )


if __name__ == "__main__":
    unittest.main()
