"""Gemini CLI hooks must use the event-specific output schema.

Gemini's current hook contract injects turn context from BeforeAgent and
post-tool context from AfterTool through hookSpecificOutput.additionalContext.
BeforeTool is for argument validation/rewriting and BeforeModel does not expose
an additionalContext field, so neither event should carry plan recitation.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
GEMINI_DIR = REPO / ".gemini"
GEMINI_HOOKS = GEMINI_DIR / "hooks"
SETTINGS = GEMINI_DIR / "settings.json"
GEMINI_DOC = REPO / "docs" / "gemini.md"
SH = shutil.which("sh")
BASH = (
    shutil.which("bash", path=str(Path(SH).parent))
    if os.name == "nt" and SH
    else shutil.which("bash")
)


def shell_python_is_usable() -> bool:
    if not BASH:
        return False
    result = subprocess.run(
        [
            str(BASH),
            "-c",
            'PY=$(command -v python3 || command -v python); [ -n "$PY" ] && "$PY" -I -c "import json"',
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    return result.returncode == 0


@unittest.skipUnless(BASH, "bash is not available")
class GeminiHookContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.cwd = Path(self._tmp.name)
        (self.cwd / "task_plan.md").write_text(
            "# Gemini schema fixture\n"
            "## Current Phase\n"
            "### Phase 1: align hooks\n"
            "**Status:** in_progress\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def run_hook(self, name: str, input_data: str = "{}") -> dict:
        result = subprocess.run(
            [str(BASH), str(GEMINI_HOOKS / name)],
            cwd=str(self.cwd),
            env=dict(os.environ, PYTHONUTF8="1"),
            input=input_data,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        return json.loads(result.stdout.lstrip("\ufeff"))

    def test_settings_register_supported_context_events(self) -> None:
        hooks = json.loads(SETTINGS.read_text(encoding="utf-8"))["hooks"]
        self.assertEqual(
            {"SessionStart", "BeforeAgent", "AfterTool", "SessionEnd"},
            set(hooks),
        )
        before_agent = hooks["BeforeAgent"][0]["hooks"][0]
        self.assertEqual("planning-before-agent", before_agent["name"])
        self.assertTrue(before_agent["command"].endswith("/.gemini/hooks/before-agent.sh"))

    def test_docs_follow_registered_events(self) -> None:
        doc = GEMINI_DOC.read_text(encoding="utf-8")
        self.assertIn("BeforeAgent", doc)
        self.assertIn("before-agent.sh", doc)
        self.assertIn("SessionEnd", doc)
        self.assertNotIn("before-tool.sh", doc)
        self.assertNotIn("before-model.sh", doc)
        self.assertFalse((GEMINI_HOOKS / "before-tool.sh").exists())
        self.assertFalse((GEMINI_HOOKS / "before-model.sh").exists())

    def test_skill_metadata_lists_registered_events(self) -> None:
        hooks = json.loads(SETTINGS.read_text(encoding="utf-8"))["hooks"]
        skill = (GEMINI_DIR / "skills" / "planning-with-files" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        frontmatter = skill.split("---", 2)[1]
        line = next(
            entry for entry in frontmatter.splitlines()
            if entry.strip().startswith("hooks:")
        )
        listed = line[line.index("(") + 1:line.rindex(")")]
        self.assertEqual(set(hooks), {event.strip() for event in listed.split(",")})

    def test_before_agent_injects_plan_as_hook_specific_context(self) -> None:
        if not shell_python_is_usable():
            self.skipTest("shell Python is not usable")
        payload = self.run_hook("before-agent.sh", '{"prompt":"continue the work"}')
        self.assertNotIn("additionalContext", payload)
        self.assertNotIn("systemMessage", payload)
        context = payload["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Gemini schema fixture", context)
        self.assertIn("align hooks", context)

    def test_after_tool_nudge_is_agent_context_not_user_message(self) -> None:
        payload = self.run_hook(
            "after-tool.sh",
            '{"tool_name":"write_file","tool_input":{},"tool_response":{}}',
        )
        self.assertNotIn("additionalContext", payload)
        self.assertNotIn("systemMessage", payload)
        context = payload["hookSpecificOutput"]["additionalContext"]
        self.assertIn("progress.md", context)
        self.assertIn("task_plan.md", context)

    def test_context_hooks_are_noop_without_a_plan(self) -> None:
        (self.cwd / "task_plan.md").unlink()
        self.assertEqual({}, self.run_hook("before-agent.sh", '{"prompt":"hello"}'))
        self.assertEqual({}, self.run_hook("after-tool.sh"))


if __name__ == "__main__":
    unittest.main()
