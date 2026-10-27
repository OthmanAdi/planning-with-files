"""Copilot hook stdout shapes match the documented command-hook contracts.

sessionStart and postToolUse return top-level `{"additionalContext": "..."}`.
PreToolUse has no documented plan-context transport; those scripts emit `{}`
and must not nest permissionDecision or additionalContext. Context nested under
`hookSpecificOutput` is the legacy VS Code Local shape, which the current
Copilot harness does not read. These tests run the real scripts and parse the
stdout the host would consume.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
HOOKS = REPO / ".github" / "hooks" / "scripts"
SH = shutil.which("sh")
# Use the same Git for Windows installation, not a WSL bash launcher.
BASH = shutil.which("bash", path=str(Path(SH).parent)) if os.name == "nt" and SH else shutil.which("bash")
POWERSHELL = (
    shutil.which("pwsh")
    or shutil.which("powershell.exe")
    or shutil.which("powershell")
)

SENTINEL = "# CONTEXT_SENTINEL 中文 ไทย Grüße"
POST_TOOL_REMINDER = "[planning-with-files] Update progress.md"


def shell_python_is_usable() -> bool:
    """True when bash can run python3 or python, as session-start.sh needs."""
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


class CopilotHookSchemaMixin:
    """Shared assertions; subclasses provide `command` for one shell."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="pwf-copilot-schema-")
        self.cwd = Path(self._tmp.name)
        (self.cwd / "task_plan.md").write_text(SENTINEL + "\n", encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def command(self, name: str) -> list[str]:
        raise NotImplementedError

    def run_hook(self, name: str, disabled: bool = False) -> dict:
        env = dict(os.environ)
        env.pop("PLANNING_DISABLED", None)
        if disabled:
            env["PLANNING_DISABLED"] = "1"
        result = subprocess.run(
            self.command(name),
            cwd=str(self.cwd),
            env=env,
            input="{}",
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        return json.loads(result.stdout.lstrip("﻿"))

    def test_session_start_returns_plan_as_top_level_context(self) -> None:
        payload = self.run_hook("session-start")
        self.assertEqual({"additionalContext"}, set(payload))
        self.assertIn(SENTINEL, payload["additionalContext"])

    def test_post_tool_use_returns_reminder_as_top_level_context(self) -> None:
        payload = self.run_hook("post-tool-use")
        self.assertEqual({"additionalContext"}, set(payload))
        self.assertIn(POST_TOOL_REMINDER, payload["additionalContext"])

    def _assert_pre_tool_is_empty(self, payload: dict) -> None:
        self.assertEqual({}, payload)

    def test_pre_tool_use_empty_with_nonempty_plan(self) -> None:
        self._assert_pre_tool_is_empty(self.run_hook("pre-tool-use"))

    def test_pre_tool_use_empty_with_empty_plan(self) -> None:
        (self.cwd / "task_plan.md").write_text("", encoding="utf-8")
        self._assert_pre_tool_is_empty(self.run_hook("pre-tool-use"))

    def test_pre_tool_use_empty_with_no_plan(self) -> None:
        (self.cwd / "task_plan.md").unlink()
        self._assert_pre_tool_is_empty(self.run_hook("pre-tool-use"))

    def test_pre_tool_use_empty_when_disabled(self) -> None:
        self._assert_pre_tool_is_empty(self.run_hook("pre-tool-use", disabled=True))

    def test_disabled_hooks_return_empty_json(self) -> None:
        for name in ("session-start", "post-tool-use"):
            with self.subTest(hook=name):
                self.assertEqual({}, self.run_hook(name, disabled=True))


@unittest.skipUnless(shell_python_is_usable(), "bash with a usable Python is not available")
class CopilotShellHookSchemaTests(CopilotHookSchemaMixin, unittest.TestCase):
    def command(self, name: str) -> list[str]:
        # Copilot runs these scripts from the "bash" key of the hook manifest.
        return [str(BASH), str(HOOKS / f"{name}.sh")]


@unittest.skipUnless(POWERSHELL, "PowerShell is not available")
class CopilotPowerShellHookSchemaTests(CopilotHookSchemaMixin, unittest.TestCase):
    def command(self, name: str) -> list[str]:
        return [
            str(POWERSHELL),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(HOOKS / f"{name}.ps1"),
        ]


if __name__ == "__main__":
    unittest.main()
