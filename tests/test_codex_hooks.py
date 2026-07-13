import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
CODEX_ROOT = REPO_ROOT / ".codex"
HOOKS_JSON = CODEX_ROOT / "hooks.json"
HOOKS_DIR = CODEX_ROOT / "hooks"


class CodexHooksTests(unittest.TestCase):
    def run_python_hook(self, script_name: str, payload: dict, cwd: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(HOOKS_DIR / script_name)],
            input=json.dumps(payload),
            text=True,
            encoding="utf-8",
            capture_output=True,
            cwd=str(cwd),
            check=False,
        )

    def run_shell_hook(self, script_name: str, cwd: Path, env: dict | None = None) -> subprocess.CompletedProcess[str]:
        shell_env = (env or os.environ).copy()
        shell = shutil.which("sh", path=shell_env.get("PATH"))
        if os.name == "nt":
            sys.path.insert(0, str(HOOKS_DIR))
            try:
                import codex_hook_adapter as adapter

                shell, extra_path_dirs = adapter._windows_git_bash()
            finally:
                sys.path.pop(0)
            if shell is None:
                raise unittest.SkipTest("Git for Windows sh.exe is unavailable")
            if extra_path_dirs:
                shell_env["PATH"] = os.pathsep.join(
                    [*extra_path_dirs, shell_env.get("PATH", "")]
                )
            shell_env.setdefault("PYTHON_BIN", sys.executable)
        elif shell is None:
            raise unittest.SkipTest("POSIX sh is unavailable")
        return subprocess.run(
            [shell, str(HOOKS_DIR / script_name)],
            text=True,
            encoding="utf-8",
            capture_output=True,
            cwd=str(cwd),
            env=shell_env,
            check=False,
        )

    def run_windows_front_door(self, sh_script: str, payload: dict, cwd: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(HOOKS_DIR / "run_sh.py"), sh_script],
            input=json.dumps(payload),
            text=True,
            encoding="utf-8",
            capture_output=True,
            cwd=str(cwd),
            check=False,
        )

    def test_hooks_json_declares_all_expected_codex_events(self) -> None:
        self.assertTrue(HOOKS_JSON.exists(), ".codex/hooks.json is missing")

        payload = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))
        self.assertEqual(
            {
                "SessionStart",
                "UserPromptSubmit",
                "PreToolUse",
                "PermissionRequest",
                "PostToolUse",
                "PreCompact",
                "Stop",
            },
            set(payload["hooks"]),
        )
        self.assertEqual(
            "startup|resume|clear|compact",
            payload["hooks"]["SessionStart"][0]["matcher"],
        )

    def test_permission_request_adapter_emits_plan_reminder(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            root.joinpath("task_plan.md").write_text(
                "# Task Plan\n### Phase 1\n- **Status:** in_progress\n",
                encoding="utf-8",
            )

            result = self.run_python_hook(
                "permission_request.py",
                {"cwd": str(root), "tool_name": "Bash"},
                root,
            )

        self.assertEqual(0, result.returncode, result.stderr)
        payload = json.loads(result.stdout)
        self.assertIn("systemMessage", payload)
        self.assertIn("Active plan", payload["systemMessage"])

    def test_permission_request_silent_without_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            result = self.run_python_hook(
                "permission_request.py",
                {"cwd": str(root), "tool_name": "Bash"},
                root,
            )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("", result.stdout.strip())

    def test_permission_request_resolves_scoped_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            plan_dir = root / ".planning" / "task-a"
            plan_dir.mkdir(parents=True)
            plan_dir.joinpath("task_plan.md").write_text("# Scoped Plan\n", encoding="utf-8")
            root.joinpath(".planning", ".active_plan").write_text("task-a\n", encoding="utf-8")

            result = self.run_python_hook(
                "permission_request.py",
                {"cwd": str(root), "tool_name": "Bash"},
                root,
            )

        self.assertEqual(0, result.returncode, result.stderr)
        payload = json.loads(result.stdout)
        self.assertIn("Active plan", payload["systemMessage"])

    def test_session_start_reuses_plan_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, tempfile.TemporaryDirectory() as home:
            root = Path(tmpdir)
            root.joinpath("task_plan.md").write_text(
                "# Task Plan\n\n## Goal\nShip Codex hooks\n",
                encoding="utf-8",
            )
            root.joinpath("progress.md").write_text(
                "# Progress\n\nFinished adapter draft.\n",
                encoding="utf-8",
            )
            root.joinpath("findings.md").write_text(
                "# Findings\n\n- reuse cursor hooks\n",
                encoding="utf-8",
            )

            env = os.environ.copy()
            env["HOME"] = home
            result = self.run_shell_hook("session-start.sh", root, env=env)

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("ACTIVE PLAN", result.stdout)
        self.assertIn("Ship Codex hooks", result.stdout)
        self.assertIn("Finished adapter draft", result.stdout)

    def test_pre_tool_use_adapter_emits_additional_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            root.joinpath("task_plan.md").write_text(
                textwrap.dedent(
                    """\
                    # Task Plan
                    ### Phase 1: Discovery
                    - **Status:** complete
                    """
                ),
                encoding="utf-8",
            )

            result = self.run_python_hook(
                "pre_tool_use.py",
                {"cwd": str(root), "tool_input": {"command": "pwd"}},
                root,
            )

        self.assertEqual(0, result.returncode, result.stderr)
        payload = json.loads(result.stdout)
        hook_output = payload["hookSpecificOutput"]
        self.assertEqual("PreToolUse", hook_output["hookEventName"])
        self.assertIn("# Task Plan", hook_output["additionalContext"])

    def test_pre_tool_use_adapter_preserves_unicode_as_ascii_safe_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            root.joinpath("task_plan.md").write_text("# \u4efb\u52a1\u8ba1\u5212\n", encoding="utf-8")

            result = self.run_python_hook(
                "pre_tool_use.py",
                {"cwd": str(root), "tool_input": {"command": "pwd"}},
                root,
            )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue(result.stdout.isascii())
        payload = json.loads(result.stdout)
        self.assertIn("\u4efb\u52a1\u8ba1\u5212", payload["hookSpecificOutput"]["additionalContext"])

    def test_post_tool_use_adapter_emits_progress_reminder(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            root.joinpath("task_plan.md").write_text("# Task Plan\n", encoding="utf-8")

            result = self.run_python_hook(
                "post_tool_use.py",
                {"cwd": str(root), "tool_response": "ok"},
                root,
            )

        self.assertEqual(0, result.returncode, result.stderr)
        payload = json.loads(result.stdout)
        self.assertIn("progress.md", payload["systemMessage"])

    def test_pre_compact_emits_flush_reminder(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            root.joinpath("task_plan.md").write_text("# Task Plan\n", encoding="utf-8")
            root.joinpath(".plan-attestation").write_text("abc123\n", encoding="utf-8")

            result = self.run_shell_hook("pre-compact.sh", root)

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("[planning-with-files] PreCompact", result.stdout)
        self.assertIn("progress.md", result.stdout)
        self.assertIn("Plan-SHA256", result.stdout)

    def test_pre_compact_silent_without_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            result = self.run_shell_hook("pre-compact.sh", root)

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("", result.stdout.strip())

    def test_stop_adapter_reports_incomplete_plan_without_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            root.joinpath("task_plan.md").write_text(
                textwrap.dedent(
                    """\
                    ### Phase 1: Discovery
                    - **Status:** complete

                    ### Phase 2: Implementation
                    - **Status:** pending
                    """
                ),
                encoding="utf-8",
            )

            first = self.run_python_hook(
                "stop.py",
                {"cwd": str(root), "stop_hook_active": False},
                root,
            )
            second = self.run_python_hook(
                "stop.py",
                {"cwd": str(root), "stop_hook_active": True},
                root,
            )

        self.assertEqual(0, first.returncode, first.stderr)
        self.assertEqual(0, second.returncode, second.stderr)

        first_payload = json.loads(first.stdout)
        second_payload = json.loads(second.stdout)

        self.assertNotIn("decision", first_payload)
        self.assertNotIn("reason", first_payload)
        self.assertIn("Task in progress", first_payload["systemMessage"])
        self.assertIn("progress.md is up to date", first_payload["systemMessage"])
        self.assertNotIn("continue working", first_payload["systemMessage"])
        self.assertIn("Task in progress", second_payload["systemMessage"])

    def test_every_hook_has_windows_override_without_posix_isms(self) -> None:
        """issue #201: on Windows Codex runs commandWindows, not the POSIX command.

        Every hook must carry a commandWindows routed through pwf-hook.cmd, and it
        must contain none of the tokens that break under the Windows interpreter
        (python3 alias stub, /dev/null, $HOME, the missing `true` command). Runs on
        every OS so unix CI also enforces the JSON stays valid and the keys stay.
        """
        payload = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))
        for event, entries in payload["hooks"].items():
            for entry in entries:
                for hook in entry["hooks"]:
                    cw = hook.get("commandWindows", "")
                    self.assertTrue(cw, f"{event} hook is missing commandWindows")
                    self.assertIn("pwf-hook.cmd", cw, f"{event} commandWindows not routed through the launcher")
                    for bad in ("$HOME", "2>/dev/null", "|| true", "python3 "):
                        self.assertNotIn(bad, cw, f"{event} commandWindows still contains POSIX-ism {bad!r}")

    def test_adapter_uses_explicit_utf8_for_shell_output(self) -> None:
        sys.path.insert(0, str(HOOKS_DIR))
        try:
            import codex_hook_adapter as adapter

            completed = subprocess.CompletedProcess(["sh"], 0, "ok\n", "")
            with mock.patch.object(adapter, "_windows_git_bash", return_value=("sh", [])), mock.patch.object(
                adapter.subprocess, "run", return_value=completed
            ) as run:
                stdout, stderr = adapter.run_shell_script("user-prompt-submit.sh", Path.cwd())
        finally:
            sys.path.pop(0)

        self.assertEqual("ok", stdout)
        self.assertEqual("", stderr)
        self.assertEqual("utf-8", run.call_args.kwargs["encoding"])
        self.assertEqual("replace", run.call_args.kwargs["errors"])

    def test_emit_json_is_ascii_safe_and_round_trips_unicode(self) -> None:
        sys.path.insert(0, str(HOOKS_DIR))
        try:
            import codex_hook_adapter as adapter

            buffer = io.BytesIO()
            stream = io.TextIOWrapper(buffer, encoding="ascii")
            with mock.patch.object(adapter.sys, "stdout", stream):
                adapter.emit_json({"message": "\u4e2d\u6587"})
                stream.flush()
            raw = buffer.getvalue().decode("ascii")
            stream.detach()
        finally:
            sys.path.pop(0)

        self.assertTrue(raw.isascii())
        self.assertEqual("\u4e2d\u6587", json.loads(raw)["message"])

    @unittest.skipUnless(os.name == "nt", "commandWindows path is Windows-only")
    def test_run_sh_front_door_serializes_shell_events_on_windows(self) -> None:
        """End-to-end Windows path emits event-appropriate Codex JSON."""
        sys.path.insert(0, str(HOOKS_DIR))
        try:
            import codex_hook_adapter as adapter
            sh_path, _ = adapter._windows_git_bash()
        finally:
            sys.path.pop(0)
        if sh_path is None:
            self.skipTest("Git for Windows sh.exe not resolvable on this runner")

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            root.joinpath("task_plan.md").write_text(
                "# \u4efb\u52a1\u8ba1\u5212\n\n## Goal\nWindows hook parity\n", encoding="utf-8"
            )
            root.joinpath("progress.md").write_text("# Progress\n", encoding="utf-8")

            user_prompt = self.run_windows_front_door("user-prompt-submit.sh", {"cwd": str(root)}, root)
            session_start = self.run_windows_front_door("session-start.sh", {"cwd": str(root)}, root)
            pre_compact = self.run_windows_front_door("pre-compact.sh", {"cwd": str(root)}, root)

        for result in (user_prompt, session_start, pre_compact):
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue(result.stdout.isascii())

        user_payload = json.loads(user_prompt.stdout)
        self.assertEqual("UserPromptSubmit", user_payload["hookSpecificOutput"]["hookEventName"])
        self.assertIn("Windows hook parity", user_payload["hookSpecificOutput"]["additionalContext"])
        self.assertIn("\u4efb\u52a1\u8ba1\u5212", user_payload["hookSpecificOutput"]["additionalContext"])

        session_payload = json.loads(session_start.stdout)
        self.assertEqual("SessionStart", session_payload["hookSpecificOutput"]["hookEventName"])
        self.assertIn("Windows hook parity", session_payload["hookSpecificOutput"]["additionalContext"])

        compact_payload = json.loads(pre_compact.stdout)
        self.assertTrue(compact_payload["continue"])
        self.assertIn("PreCompact", compact_payload["systemMessage"])


if __name__ == "__main__":
    unittest.main()
