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
            python_stub = bin_dir / "python3"
            python_stub.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
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


if __name__ == "__main__":
    unittest.main()
