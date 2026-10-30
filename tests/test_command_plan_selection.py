"""Claude plugin command prompts follow the selected-plan contract (issue #350).

The skill and resolver bind one selected task and refuse ambiguous or rejected
selectors. These checks keep the command prompts from drifting back to the
legacy root-file workflow or the newest-plan fallback, without freezing prose.
"""
from __future__ import annotations

import unittest
from pathlib import Path


COMMANDS_DIR = Path(__file__).resolve().parents[1] / "commands"

CREATION_COMMANDS = ("plan.md", "pwf.md")
SELECTION_COMMANDS = ("plan.md", "pwf.md", "status.md", "plan-goal.md")
ALL_COMMANDS = CREATION_COMMANDS + ("status.md", "plan-attest.md", "plan-goal.md")


def _read(name: str) -> str:
    return (COMMANDS_DIR / name).read_text(encoding="utf-8")


class CommandPlanSelectionTests(unittest.TestCase):
    def test_no_legacy_root_or_newest_fallback_instructions(self) -> None:
        for name in ALL_COMMANDS:
            with self.subTest(command=name):
                body = _read(name)
                self.assertNotIn("in the current project directory", body)
                self.assertNotIn("from the current project directory", body)
                self.assertNotIn("then newest `.planning/<dir>/`, then legacy", body)

    def test_selection_uses_resolver_and_refuses_ambiguity(self) -> None:
        for name in SELECTION_COMMANDS:
            with self.subTest(command=name):
                body = _read(name)
                self.assertIn("resolve-plan-dir.sh", body)
                self.assertIn("resolve-plan-dir.ps1", body)
                self.assertIn("--check-ambiguity", body)
                self.assertIn("PWF_PLAN_AMBIGUOUS_V1", body)
                self.assertIn("PWF_PLAN_ROOT", body)
                self.assertIn("legacy", body)

    def test_attest_documents_multi_plan_refusal(self) -> None:
        body = _read("plan-attest.md")
        self.assertIn("Multiple plans are available", body)
        self.assertIn("never falls back to another plan", body)

    def test_creation_aliases_initialize_and_validate(self) -> None:
        for name in CREATION_COMMANDS:
            with self.subTest(command=name):
                body = _read(name)
                self.assertIn("init-session.sh", body)
                self.assertIn("init-session.ps1", body)
                self.assertIn("check-complete.sh --validate", body)
                self.assertIn("check-complete.ps1 -Validate", body)
                self.assertIn("### Phase N:", body)
                self.assertIn("never overwrite existing planning files", body)

    def test_shared_pointer_is_not_a_session_binding(self) -> None:
        for name in ALL_COMMANDS:
            with self.subTest(command=name):
                self.assertIn("does not bind a parallel session", _read(name))


if __name__ == "__main__":
    unittest.main()
