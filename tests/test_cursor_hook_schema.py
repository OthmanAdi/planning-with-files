"""Cursor adapter manifests and command output follow the current hook schema."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CURSOR_ROOT = REPO_ROOT / ".cursor"
HOOKS = CURSOR_ROOT / "hooks"
UNSUPPORTED_EVENTS = {"userPromptSubmit"}


def shell_python_is_usable() -> bool:
    """True when python3 or python runs from sh, as session-start.sh needs."""
    sh = shutil.which("sh")
    if not sh:
        return False
    probe = (
        'for PY in "$(command -v python3)" "$(command -v python)"; do '
        '[ -n "$PY" ] && "$PY" -I -c "import json" && exit 0; done; exit 1'
    )
    result = subprocess.run(
        [sh, "-c", probe], capture_output=True, text=True, timeout=30, check=False
    )
    return result.returncode == 0


class CursorHookSchemaTests(unittest.TestCase):
    def test_manifests_only_use_supported_prompt_and_permission_events(self) -> None:
        for manifest_name in ("hooks.json", "hooks.windows.json"):
            with self.subTest(manifest=manifest_name):
                manifest = json.loads((CURSOR_ROOT / manifest_name).read_text())
                hooks = manifest["hooks"]
                self.assertTrue(UNSUPPORTED_EVENTS.isdisjoint(hooks))
                self.assertIn("sessionStart", hooks)
                self.assertIn("preToolUse", hooks)
                self.assertIn("postToolUse", hooks)
                self.assertIn("session-start", hooks["sessionStart"][0]["command"])
                if manifest_name == "hooks.windows.json":
                    for entries in hooks.values():
                        for entry in entries:
                            self.assertIn("-NoProfile", entry["command"])

    @unittest.skipUnless(shutil.which("sh"), "requires POSIX sh")
    def test_shell_session_start_emits_plan_as_additional_context(self) -> None:
        with tempfile.TemporaryDirectory(prefix="pwf-cursor-schema-") as tmp:
            root = Path(tmp)
            (root / "task_plan.md").write_text("# SESSION-START-PLAN\n", encoding="utf-8")
            (root / "progress.md").write_text("Recent progress\n", encoding="utf-8")
            env = os.environ.copy()
            env.pop("PLANNING_DISABLED", None)

            result = subprocess.run(
                ["sh", str(HOOKS / "session-start.sh")],
                cwd=root,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertIn("SESSION-START-PLAN", payload["additional_context"])

    @unittest.skipUnless(shutil.which("sh"), "requires POSIX sh")
    def test_shell_session_start_returns_valid_json_when_python_fails(self) -> None:
        with tempfile.TemporaryDirectory(prefix="pwf-cursor-schema-") as tmp:
            root = Path(tmp)
            (root / "task_plan.md").write_text("# SESSION-START-PLAN\n", encoding="utf-8")
            bin_dir = root / "bin"
            bin_dir.mkdir()
            # The hook falls back from python3 to python, so both must fail.
            for name in ("python3", "python"):
                python_stub = bin_dir / name
                python_stub.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8", newline="\n")
                python_stub.chmod(0o755)
            env = os.environ.copy()
            env.pop("PLANNING_DISABLED", None)
            env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")

            result = subprocess.run(
                ["sh", str(HOOKS / "session-start.sh")],
                cwd=root,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual({}, json.loads(result.stdout))

    @unittest.skipUnless(shutil.which("sh"), "requires POSIX sh")
    def test_shell_permission_and_post_tool_hooks_emit_schema_fields(self) -> None:
        with tempfile.TemporaryDirectory(prefix="pwf-cursor-schema-") as tmp:
            root = Path(tmp)
            (root / "task_plan.md").write_text("# Active plan\n", encoding="utf-8")
            env = os.environ.copy()
            env.pop("PLANNING_DISABLED", None)

            pre_tool = subprocess.run(
                ["sh", str(HOOKS / "pre-tool-use.sh")],
                cwd=root,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            post_tool = subprocess.run(
                ["sh", str(HOOKS / "post-tool-use.sh")],
                cwd=root,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, pre_tool.returncode, pre_tool.stderr)
            self.assertEqual({"permission": "allow"}, json.loads(pre_tool.stdout))
            self.assertEqual(0, post_tool.returncode, post_tool.stderr)
            self.assertIn(
                "additional_context", json.loads(post_tool.stdout)
            )

    def test_shell_session_start_runs_python_isolated(self) -> None:
        # Hook interpreters run with -I (v3.17.0), so a json.py planted in the
        # project directory is never imported by the hook.
        text = (HOOKS / "session-start.sh").read_text(encoding="utf-8")
        invocations = [line for line in text.splitlines() if '"$PYTHON"' in line]
        self.assertTrue(invocations, "no Python invocation found in session-start.sh")
        for line in invocations:
            self.assertIn('"$PYTHON" -I -X utf8 ', line)

    @unittest.skipUnless(shell_python_is_usable(), "shell Python is not usable")
    def test_shell_session_start_ignores_project_json_module(self) -> None:
        with tempfile.TemporaryDirectory(prefix="pwf-cursor-schema-") as tmp:
            root = Path(tmp)
            (root / "task_plan.md").write_text("# ISOLATED-PLAN\n", encoding="utf-8")
            (root / "json.py").write_text(
                "open('PLANTED_json', 'w').close()\nraise RuntimeError('shadow loaded')\n",
                encoding="utf-8",
            )
            env = os.environ.copy()
            env.pop("PLANNING_DISABLED", None)

            result = subprocess.run(
                ["sh", str(HOOKS / "session-start.sh")],
                cwd=root,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertFalse(
                (root / "PLANTED_json").exists(),
                "session-start.sh imported the project json.py",
            )
            self.assertIn(
                "ISOLATED-PLAN", json.loads(result.stdout)["additional_context"]
            )


if __name__ == "__main__":
    unittest.main()
