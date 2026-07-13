"""Integration tests: Codex hooks use resolve-plan-dir.sh to find the active plan.

These tests confirm that after the #148 fix, all four Codex hook shell scripts
correctly locate task_plan.md through the resolver rather than assuming the
legacy root path. They complement the unit tests in test_resolve_plan_dir.py
by exercising the full hook→resolver→plan-file chain.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
HOOKS_DIR = REPO_ROOT / ".codex" / "hooks"


def shell_and_env() -> tuple[str, dict[str, str]]:
    env = os.environ.copy()
    if os.name != "nt":
        shell = shutil.which("sh")
        if shell is None:
            raise unittest.SkipTest("POSIX sh is unavailable")
        return shell, env

    sys.path.insert(0, str(HOOKS_DIR))
    try:
        import codex_hook_adapter as adapter

        shell, extra_path_dirs = adapter._windows_git_bash()
    finally:
        sys.path.pop(0)
    if shell is None:
        raise unittest.SkipTest("Git for Windows sh.exe is unavailable")
    if extra_path_dirs:
        env["PATH"] = os.pathsep.join([*extra_path_dirs, env.get("PATH", "")])
    env.setdefault("PYTHON_BIN", sys.executable)
    return shell, env


def run_hook(script: str, cwd: Path, env_extra: dict | None = None) -> subprocess.CompletedProcess[str]:
    shell, env = shell_and_env()
    env.pop("PLAN_ID", None)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [shell, str(HOOKS_DIR / script)],
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

    def test_global_resolver_is_a_thin_canonical_forwarder(self) -> None:
        resolver = (HOOKS_DIR / "resolve-plan-dir.sh").read_text(encoding="utf-8")
        self.assertIn("../skills/planning-with-files/scripts/resolve-plan-dir.sh", resolver)
        self.assertIn('exec sh "${CANONICAL_RESOLVER}" "$@"', resolver)
        self.assertNotIn("resolve_latest_dir()", resolver)

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

    def test_user_prompt_submit_accepts_utf8_bom_active_pointer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            safe = root / ".planning" / "safe"
            write_plan_in_dir(safe, goal="BOM-safe goal")
            decoy = root / ".planning" / "newer-decoy"
            write_plan_in_dir(decoy, goal="Newest fallback goal")
            # If BOM stripping regresses, newest-dir fallback must select the
            # decoy and make this test fail instead of masking the bug.
            os.utime(safe, (100, 100))
            os.utime(decoy, (200, 200))
            (root / ".planning" / ".active_plan").write_bytes(b"\xef\xbb\xbfsafe\n")

            result = run_hook("user-prompt-submit.sh", root)

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("BOM-safe goal", result.stdout)
            self.assertNotIn("Newest fallback goal", result.stdout)

    def test_user_prompt_submit_rejects_traversal_plan_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_plan_in_dir(root / ".planning" / "safe", goal="Workspace plan")
            write_plan_in_dir(root / "outside", goal="Escaped plan")
            (root / ".planning" / ".active_plan").write_text("safe\n", encoding="utf-8")

            result = run_hook(
                "user-prompt-submit.sh",
                root,
                env_extra={"PLAN_ID": "../outside"},
            )

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("Workspace plan", result.stdout)
            self.assertNotIn("Escaped plan", result.stdout)

    def test_user_prompt_submit_rejects_external_symlink_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside_tmp:
            root = Path(tmp)
            safe = root / ".planning" / "safe"
            outside = Path(outside_tmp) / "outside"
            write_plan_in_dir(safe, goal="Workspace plan")
            write_plan_in_dir(outside, goal="Escaped plan")
            (root / ".planning" / ".active_plan").write_text("safe\n", encoding="utf-8")
            escape = root / ".planning" / "escape"
            try:
                try:
                    escape.symlink_to(outside, target_is_directory=True)
                except OSError as symlink_error:
                    if os.name != "nt":
                        self.skipTest(f"directory symlinks are unavailable: {symlink_error}")
                    junction = subprocess.run(
                        ["cmd", "/d", "/c", "mklink", "/J", str(escape), str(outside)],
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        capture_output=True,
                        check=False,
                    )
                    if junction.returncode != 0:
                        self.skipTest("directory symlinks and junctions are unavailable")

                result = run_hook(
                    "user-prompt-submit.sh",
                    root,
                    env_extra={"PLAN_ID": "escape"},
                )

                self.assertEqual(0, result.returncode, result.stderr)
                self.assertIn("Workspace plan", result.stdout)
                self.assertNotIn("Escaped plan", result.stdout)
            finally:
                if escape.is_symlink():
                    escape.unlink()
                elif os.name == "nt" and escape.exists():
                    # os.rmdir removes the junction itself, never its target.
                    os.rmdir(escape)

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
