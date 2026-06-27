"""Tests for scripts/set-active-plan.sh — companion to resolve-plan-dir.sh.

set-active-plan.sh lets users explicitly switch the active plan pointer
without needing to export PLAN_ID. This is the UX complement to slug-mode
init-session.sh for parallel multi-task workflows (#148).
"""
from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SET_ACTIVE_SH = REPO_ROOT / "scripts" / "set-active-plan.sh"


def run_set_active(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["sh", str(SET_ACTIVE_SH), *args],
        cwd=str(cwd),
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )


class SetActivePlanTests(unittest.TestCase):

    def test_script_exists(self) -> None:
        self.assertTrue(SET_ACTIVE_SH.exists(), "scripts/set-active-plan.sh missing")

    def test_no_args_no_active_plan_prints_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run_set_active(Path(tmp))
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("No active plan", result.stdout)

    def test_no_args_shows_current_active_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = root / ".planning" / "2026-01-10-my-task"
            plan.mkdir(parents=True)
            (root / ".planning" / ".active_plan").write_text("2026-01-10-my-task\n", encoding="utf-8")
            result = run_set_active(root)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("2026-01-10-my-task", result.stdout)

    def test_sets_active_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan_a = root / ".planning" / "task-a"
            plan_b = root / ".planning" / "task-b"
            plan_a.mkdir(parents=True)
            plan_b.mkdir(parents=True)
            # Set to task-a first
            r1 = run_set_active(root, "task-a")
            self.assertEqual(0, r1.returncode, r1.stderr)
            active = (root / ".planning" / ".active_plan").read_text(encoding="utf-8").strip()
            self.assertEqual("task-a", active)
            # Switch to task-b
            r2 = run_set_active(root, "task-b")
            self.assertEqual(0, r2.returncode, r2.stderr)
            active = (root / ".planning" / ".active_plan").read_text(encoding="utf-8").strip()
            self.assertEqual("task-b", active)

    def test_errors_on_nonexistent_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_set_active(root, "ghost-plan")
            self.assertNotEqual(0, result.returncode)
            self.assertIn("not found", result.stderr)

    def test_resolver_picks_up_newly_set_plan(self) -> None:
        # End-to-end: set-active-plan.sh then resolve-plan-dir.sh returns correct dir
        from pathlib import Path as P
        resolve_sh = REPO_ROOT / "scripts" / "resolve-plan-dir.sh"
        with tempfile.TemporaryDirectory() as tmp:
            root = P(tmp)
            plan_a = root / ".planning" / "2026-task-a"
            plan_b = root / ".planning" / "2026-task-b"
            plan_a.mkdir(parents=True)
            plan_b.mkdir(parents=True)
            (plan_a / "task_plan.md").write_text("# A\n", encoding="utf-8")
            (plan_b / "task_plan.md").write_text("# B\n", encoding="utf-8")
            # Pin to task-a
            run_set_active(root, "2026-task-a")
            result = subprocess.run(
                ["sh", str(resolve_sh)],
                cwd=str(root),
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=False,
            )
            self.assertTrue(result.stdout.strip().endswith("2026-task-a"))
            # Switch to task-b
            run_set_active(root, "2026-task-b")
            result = subprocess.run(
                ["sh", str(resolve_sh)],
                cwd=str(root),
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=False,
            )
            self.assertTrue(result.stdout.strip().endswith("2026-task-b"))


if __name__ == "__main__":
    unittest.main()
