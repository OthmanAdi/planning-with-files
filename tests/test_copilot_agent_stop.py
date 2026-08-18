"""Behavior tests for the GitHub Copilot AgentStop hooks."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
AGENT_STOP_PS1 = REPO_ROOT / ".github" / "hooks" / "scripts" / "agent-stop.ps1"
POWERSHELL = (
    shutil.which("pwsh")
    or shutil.which("powershell.exe")
    or shutil.which("powershell")
)


@unittest.skipUnless(POWERSHELL, "PowerShell is not available")
class CopilotAgentStopPowerShellTests(unittest.TestCase):
    def test_unstructured_plan_emits_empty_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            (cwd / "task_plan.md").write_text(
                "# Notes\n\nThis file has no phase structure.\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    str(POWERSHELL),
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(AGENT_STOP_PS1),
                ],
                cwd=cwd,
                input="{}",
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual({}, json.loads(result.stdout.lstrip("\ufeff")))


if __name__ == "__main__":
    unittest.main()
