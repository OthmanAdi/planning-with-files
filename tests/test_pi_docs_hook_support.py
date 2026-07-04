"""Documentation contract for Pi hook adaptation.

After full adaptation, Pi docs must no longer state that hooks are unsupported.
"""
from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PI_DOC = REPO_ROOT / "docs" / "pi-agent.md"
PI_SKILL_README = REPO_ROOT / ".pi" / "skills" / "planning-with-files" / "README.md"


UNSUPPORTED_SENTENCE = (
    "Hooks (PreToolUse, PostToolUse, Stop) are **Claude Code specific** and are not currently supported in Pi Agent."
)


class PiDocsHookSupportTests(unittest.TestCase):
    def test_docs_pi_agent_no_longer_claims_hooks_unsupported(self) -> None:
        text = PI_DOC.read_text(encoding="utf-8")
        self.assertNotIn(UNSUPPORTED_SENTENCE, text)

    def test_pi_skill_readme_no_longer_claims_hooks_unsupported(self) -> None:
        text = PI_SKILL_README.read_text(encoding="utf-8")
        self.assertNotIn(UNSUPPORTED_SENTENCE, text)

    def test_docs_describe_mode_based_behavior(self) -> None:
        text = PI_DOC.read_text(encoding="utf-8")
        self.assertIn("cache-safe", text)
        self.assertIn("parity", text)

    def test_docs_describe_plan_execute_confirmation(self) -> None:
        text = PI_DOC.read_text(encoding="utf-8")
        readme = PI_SKILL_README.read_text(encoding="utf-8")
        self.assertIn("/plan-execute", text)
        self.assertIn("/plan-execute", readme)
        self.assertIn("passive", text)
        self.assertIn("passive", readme)


if __name__ == "__main__":
    unittest.main()
