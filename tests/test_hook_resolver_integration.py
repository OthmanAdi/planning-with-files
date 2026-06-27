"""Integration tests: Codex hooks use resolve-plan-dir.sh to find the active plan.

These tests confirm that after the #148 fix, all four Codex hook shell scripts
correctly locate task_plan.md through the resolver rather than assuming the
legacy root path. They complement the unit tests in test_resolve_plan_dir.py
by exercising the full hook→resolver→plan-file chain.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
HOOKS_DIR = REPO_ROOT / ".codex" / "hooks"


def run_hook(script: str, cwd: Path, env_extra: dict | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.pop("PLAN_ID", None)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        ["sh", str(HOOKS_DIR / script)],
        cwd=str(cwd),
        text=True,
        encoding="utf-8",
        capture_output=True,
        env=env,
        check=False,
    )


def write_plan_in_dir(plan_dir: Path, goal: str = "Ship the feature") -> None:
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "task_plan.md").write_text(
        f"# Task Plan\n\n## Goal\n{goal}\n\n### Phase 1: Work\n- **Status:** in_progress\n",
        encoding="utf-8",
    )
    (plan_dir / "progress.md").write_text("# Progress\n\nstarted\n", encoding="utf-8")
    (plan_dir / "findings.md").write_text("# Findings\n", encoding="utf-8")


class HookResolverIntegrationTests(unittest.TestCase):

    # ------------------------------------------------------------------
    # user-prompt-submit.sh
    # ------------------------------------------------------------------

    def test_user_prompt_submit_silent_with_no_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run_hook("user-prompt-submit.sh", Path(tmp))
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertNotIn("ACTIVE PLAN", result.stdout)

    def test_user_prompt_submit_injects_from_planning_subdir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan_dir = root / ".planning" / "2026-01-10-backend-refactor"
            write_plan_in_dir(plan_dir, goal="Refactor the auth layer")
            (root / ".planning" / ".active_plan").write_text(
                "2026-01-10-backend-refactor\n", encoding="utf-8"
            )
            result = run_hook("user-prompt-submit.sh", root)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("ACTIVE PLAN", result.stdout)
            self.assertIn("Refactor the auth layer", result.stdout)

    def test_user_prompt_submit_legacy_root_still_works(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "task_plan.md").write_text(
                "# Task Plan\n\n## Goal\nLegacy goal\n\n### Phase 1: Work\n- **Status:** in_progress\n",
                encoding="utf-8",
            )
            (root / "progress.md").write_text("# Progress\n", encoding="utf-8")
            result = run_hook("user-prompt-submit.sh", root)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("ACTIVE PLAN", result.stdout)
            self.assertIn("Legacy goal", result.stdout)

    def test_user_prompt_submit_env_plan_id_pins_correct_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_plan_in_dir(root / ".planning" / "task-a", goal="Task A goal")
            write_plan_in_dir(root / ".planning" / "task-b", goal="Task B goal")
            (root / ".planning" / ".active_plan").write_text("task-b\n", encoding="utf-8")
            # Override with env var to force task-a
            result = run_hook("user-prompt-submit.sh", root, env_extra={"PLAN_ID": "task-a"})
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("Task A goal", result.stdout)
            self.assertNotIn("Task B goal", result.stdout)

    # ------------------------------------------------------------------
    # pre-tool-use.sh
    # ------------------------------------------------------------------

    def test_pre_tool_use_allows_with_no_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run_hook("pre-tool-use.sh", Path(tmp))
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("allow", result.stdout)

    def test_pre_tool_use_surfaces_plan_from_subdir_on_stderr(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan_dir = root / ".planning" / "2026-01-10-my-task"
            write_plan_in_dir(plan_dir, goal="My task goal")
            (root / ".planning" / ".active_plan").write_text(
                "2026-01-10-my-task\n", encoding="utf-8"
            )
            result = run_hook("pre-tool-use.sh", root)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("allow", result.stdout)
            self.assertIn("My task goal", result.stderr)

    # ------------------------------------------------------------------
    # stop.sh
    # ------------------------------------------------------------------

    def test_stop_silent_with_no_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run_hook("stop.sh", Path(tmp))
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual("", result.stdout.strip())

    def test_stop_reports_incomplete_from_subdir_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan_dir = root / ".planning" / "2026-01-10-feature"
            write_plan_in_dir(plan_dir, goal="Build feature")
            (root / ".planning" / ".active_plan").write_text(
                "2026-01-10-feature\n", encoding="utf-8"
            )
            result = run_hook("stop.sh", root)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("followup_message", result.stdout)

    # ------------------------------------------------------------------
    # post-tool-use.sh
    # ------------------------------------------------------------------

    def test_post_tool_use_silent_with_no_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run_hook("post-tool-use.sh", Path(tmp))
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual("", result.stdout.strip())

    def test_post_tool_use_reminds_when_plan_in_subdir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan_dir = root / ".planning" / "2026-01-10-work"
            write_plan_in_dir(plan_dir)
            (root / ".planning" / ".active_plan").write_text(
                "2026-01-10-work\n", encoding="utf-8"
            )
            result = run_hook("post-tool-use.sh", root)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("progress.md", result.stdout)


if __name__ == "__main__":
    unittest.main()
