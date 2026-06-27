"""Tests for Codex session isolation — addresses #146.

Goal: a Codex session must not receive another session's plan context just because
task_plan.md exists in cwd. Each session must explicitly attach. Attach state
lives at .planning/sessions/<session_id>.attached and is opt-in.

Backward compat: if no .planning/sessions/ directory exists at all, hooks fall
back to legacy "any session in this cwd sees the plan" behavior to avoid breaking
existing single-session users on upgrade.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
HOOKS_DIR = REPO_ROOT / ".codex" / "hooks"


class CodexSessionIsolationTests(unittest.TestCase):
    def run_python_hook(
        self,
        script_name: str,
        payload: dict,
        cwd: Path,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(HOOKS_DIR / script_name)],
            input=json.dumps(payload),
            text=True,
            encoding="utf-8",
            capture_output=True,
            cwd=str(cwd),
            check=False,
        )

    def write_plan(self, root: Path) -> None:
        (root / "task_plan.md").write_text(
            "# Task Plan\n\n## Goal\nShip Codex isolation\n\n### Phase 1: Discovery\n- **Status:** in_progress\n",
            encoding="utf-8",
        )
        (root / "progress.md").write_text("# Progress\n\nstarted\n", encoding="utf-8")
        (root / "findings.md").write_text("# Findings\n", encoding="utf-8")

    def attach_session(self, root: Path, session_id: str) -> None:
        sessions_dir = root / ".planning" / "sessions"
        sessions_dir.mkdir(parents=True, exist_ok=True)
        (sessions_dir / f"{session_id}.attached").write_text("legacy\n", encoding="utf-8")

    # ------------------------------------------------------------------
    # Backward compat: no .planning/sessions/ => legacy single-session mode
    # ------------------------------------------------------------------

    def test_legacy_mode_user_prompt_submit_injects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_plan(root)
            payload = {"cwd": str(root), "session_id": "sess-A"}
            result = subprocess.run(
                ["sh", str(HOOKS_DIR / "user-prompt-submit.sh")],
                cwd=str(root),
                text=True,
                encoding="utf-8",
                capture_output=True,
                env={**os.environ, "PWF_SESSION_ID": "sess-A"},
                check=False,
            )
            self.assertIn("ACTIVE PLAN", result.stdout)

    # ------------------------------------------------------------------
    # Isolation: when sessions/ dir exists, only attached sessions see context
    # ------------------------------------------------------------------

    def test_user_prompt_submit_silent_for_unattached_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_plan(root)
            self.attach_session(root, "sess-A")
            # Session B is NOT attached
            env = {**os.environ, "PWF_SESSION_ID": "sess-B"}
            result = subprocess.run(
                ["sh", str(HOOKS_DIR / "user-prompt-submit.sh")],
                cwd=str(root),
                text=True,
                encoding="utf-8",
                capture_output=True,
                env=env,
                check=False,
            )
            self.assertNotIn("ACTIVE PLAN", result.stdout)

    def test_user_prompt_submit_injects_for_attached_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_plan(root)
            self.attach_session(root, "sess-A")
            env = {**os.environ, "PWF_SESSION_ID": "sess-A"}
            result = subprocess.run(
                ["sh", str(HOOKS_DIR / "user-prompt-submit.sh")],
                cwd=str(root),
                text=True,
                encoding="utf-8",
                capture_output=True,
                env=env,
                check=False,
            )
            self.assertIn("ACTIVE PLAN", result.stdout)
            self.assertIn("Ship Codex isolation", result.stdout)

    def test_pre_tool_use_silent_for_unattached_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_plan(root)
            self.attach_session(root, "sess-A")
            payload = {"cwd": str(root), "session_id": "sess-B"}
            result = self.run_python_hook("pre_tool_use.py", payload, root)
            self.assertEqual(0, result.returncode, result.stderr)
            # No systemMessage payload should be emitted
            stdout = result.stdout.strip()
            if stdout:
                emitted = json.loads(stdout)
                self.assertNotIn("systemMessage", emitted)

    def test_stop_does_not_block_unattached_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_plan(root)
            self.attach_session(root, "sess-A")
            payload = {"cwd": str(root), "session_id": "sess-B", "stop_hook_active": False}
            result = self.run_python_hook("stop.py", payload, root)
            self.assertEqual(0, result.returncode, result.stderr)
            stdout = result.stdout.strip()
            if stdout:
                emitted = json.loads(stdout)
                self.assertNotEqual(emitted.get("decision"), "block")

    def test_two_sessions_same_cwd_isolated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_plan(root)
            self.attach_session(root, "sess-A")
            # A sees plan, B silent — single repro for cross-session leak
            env_a = {**os.environ, "PWF_SESSION_ID": "sess-A"}
            env_b = {**os.environ, "PWF_SESSION_ID": "sess-B"}
            ra = subprocess.run(
                ["sh", str(HOOKS_DIR / "user-prompt-submit.sh")],
                cwd=str(root), text=True, encoding="utf-8", capture_output=True, env=env_a, check=False,
            )
            rb = subprocess.run(
                ["sh", str(HOOKS_DIR / "user-prompt-submit.sh")],
                cwd=str(root), text=True, encoding="utf-8", capture_output=True, env=env_b, check=False,
            )
            self.assertIn("ACTIVE PLAN", ra.stdout)
            self.assertNotIn("ACTIVE PLAN", rb.stdout)


if __name__ == "__main__":
    unittest.main()
