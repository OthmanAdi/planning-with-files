"""Regression coverage for shell-adapter Python import isolation."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
SH = shutil.which("sh")
CODEX_HOOKS = REPO / ".codex" / "hooks"
GEMINI_HOOKS = REPO / ".gemini" / "hooks"
COPILOT_HOOKS = REPO / ".github" / "hooks" / "scripts"

PYTHON_SHELL_HOOKS = (
    GEMINI_HOOKS / "before-model.sh",
    GEMINI_HOOKS / "before-tool.sh",
    GEMINI_HOOKS / "session-start.sh",
    GEMINI_HOOKS / "session-end.sh",
    COPILOT_HOOKS / "session-start.sh",
    COPILOT_HOOKS / "pre-tool-use.sh",
    COPILOT_HOOKS / "error-occurred.sh",
)

CODEX_PYTHON_SHELL_HOOKS = (
    CODEX_HOOKS / "pre-tool-use.sh",
    CODEX_HOOKS / "session-start.sh",
    CODEX_HOOKS / "user-prompt-submit.sh",
)


def shell_python_is_usable() -> bool:
    if not SH:
        return False
    result = subprocess.run(
        [
            str(SH),
            "-c",
            'PY=$(command -v python3 || command -v python); [ -n "$PY" ] && "$PY" -I -c "import json"',
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    return result.returncode == 0


@unittest.skipUnless(shell_python_is_usable(), "shell Python is not usable")
class AdapterPythonIsolationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.cwd = Path(self._tmp.name)
        (self.cwd / "task_plan.md").write_text(
            "# Task Plan\n## Current Phase: hardening\n### Phase 1: Work\n"
            "**Status:** in_progress\n",
            encoding="utf-8",
        )
        (self.cwd / "json.py").write_text(
            "open('PLANTED_json', 'w').close()\nraise RuntimeError('shadow loaded')\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def run_hook(self, script: Path, input_data: str = "{}") -> dict:
        result = subprocess.run(
            [str(SH), str(script)],
            cwd=str(self.cwd),
            env=dict(os.environ),
            input=input_data,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        return json.loads(result.stdout.lstrip("\ufeff"))

    def test_gemini_json_encoding_ignores_project_json_module(self) -> None:
        for name in ("before-model.sh", "before-tool.sh"):
            with self.subTest(hook=name):
                marker = self.cwd / "PLANTED_json"
                marker.unlink(missing_ok=True)
                payload = self.run_hook(GEMINI_HOOKS / name)
                self.assertFalse(marker.exists(), f"{name} imported project json.py")
                self.assertIn("hardening", json.dumps(payload))

    def test_copilot_python_paths_ignore_project_json_module(self) -> None:
        cases = (
            ("session-start.sh", "{}"),
            ("pre-tool-use.sh", "{}"),
            ("error-occurred.sh", '{"error":{"message":"fixture failure"}}'),
        )
        for name, input_data in cases:
            with self.subTest(hook=name):
                marker = self.cwd / "PLANTED_json"
                marker.unlink(missing_ok=True)
                payload = self.run_hook(COPILOT_HOOKS / name, input_data)
                self.assertFalse(marker.exists(), f"{name} imported project json.py")
                self.assertIn("additionalContext", payload.get("hookSpecificOutput", {}))


@unittest.skipUnless(SH, "sh is not available")
class CodexPythonIsolationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.cwd = Path(self._tmp.name)
        (self.cwd / "task_plan.md").write_text(
            "# Task Plan\n### Phase 1: Work\n**Status:** in_progress\n",
            encoding="utf-8",
        )
        (self.cwd / "progress.md").write_text("# Progress\n", encoding="utf-8")
        (self.cwd / "hashlib.py").write_text(
            "open('PLANTED_hashlib', 'w').close()\nraise RuntimeError('shadow loaded')\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def run_hook(self, name: str) -> subprocess.CompletedProcess[str]:
        env = dict(os.environ)
        env["PYTHON_BIN"] = sys.executable
        env["PWF_PLAN_ROOT"] = str(self.cwd)
        return subprocess.run(
            [str(SH), str(CODEX_HOOKS / name)],
            cwd=str(self.cwd),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )

    def test_codex_shell_python_ignores_project_hashlib_module(self) -> None:
        cases = (
            ("user-prompt-submit.sh", "ACTIVE PLAN", "stdout"),
            ("pre-tool-use.sh", "# Task Plan", "stderr"),
            ("session-start.sh", "ACTIVE PLAN", "stdout"),
        )
        for name, expected, stream in cases:
            with self.subTest(hook=name):
                marker = self.cwd / "PLANTED_hashlib"
                marker.unlink(missing_ok=True)
                result = self.run_hook(name)
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertFalse(marker.exists(), f"{name} imported project hashlib.py")
                self.assertIn(expected, getattr(result, stream))


class AdapterPythonIsolationContractTests(unittest.TestCase):
    def test_every_adapter_python_invocation_uses_isolated_mode(self) -> None:
        for script in PYTHON_SHELL_HOOKS:
            with self.subTest(hook=script.relative_to(REPO)):
                text = script.read_text(encoding="utf-8")
                invocations = [
                    line
                    for line in text.splitlines()
                    if "$($PYTHON" in line or "| $PYTHON" in line
                ]
                self.assertTrue(invocations, f"no Python invocation found in {script}")
                for line in invocations:
                    self.assertIn(
                        "$PYTHON -I",
                        line,
                        f"non-isolated Python invocation in {script.relative_to(REPO)}: {line}",
                    )

    def test_every_codex_shell_python_invocation_uses_isolated_mode(self) -> None:
        variables = ('"$PYTHON_BIN"', '"$PWF_PYTHON"', '"$PIN_PYTHON"', '"$_tp_candidate"')
        for script in CODEX_PYTHON_SHELL_HOOKS:
            with self.subTest(hook=script.relative_to(REPO)):
                text = script.read_text(encoding="utf-8")
                invocations = [
                    line
                    for line in text.splitlines()
                    if any(variable in line for variable in variables)
                    and (" -c " in line or (".py\"" in line and " -f " not in line))
                ]
                self.assertTrue(invocations, f"no Python invocation found in {script}")
                for line in invocations:
                    self.assertIn(
                        " -I ",
                        line,
                        f"non-isolated Python invocation in {script.relative_to(REPO)}: {line}",
                    )


if __name__ == "__main__":
    unittest.main()
