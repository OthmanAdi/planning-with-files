"""Named-plan coverage for Cursor's native PowerShell hook route."""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CURSOR_HOOKS = REPO_ROOT / ".cursor" / "hooks"
POWERSHELL = (
    shutil.which("powershell.exe")
    or shutil.which("powershell")
    or shutil.which("pwsh")
)
SCRUB_VARS = ("PLAN_ID", "PWF_PLAN_ROOT", "PLANNING_DISABLED")


@unittest.skipUnless(POWERSHELL, "requires PowerShell")
class CursorPowerShellNamedPlanTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="pwf-cursor-ps-named-")
        self.workspace = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def clean_env(self, **extra: str) -> dict[str, str]:
        env = os.environ.copy()
        for name in SCRUB_VARS:
            env.pop(name, None)
        env.update(extra)
        return env

    def write_root_plan(self, marker: str = "ROOT-PLAN-MARKER") -> None:
        (self.workspace / "task_plan.md").write_text(
            f"# {marker}\n### Phase 1\n**Status:** pending\n",
            encoding="utf-8",
        )
        (self.workspace / "progress.md").write_text(
            "ROOT-PROGRESS-MARKER\n", encoding="utf-8"
        )

    def write_named_plan(
        self,
        slug: str,
        marker: str,
        *,
        active: bool = False,
    ) -> Path:
        plan_dir = self.workspace / ".planning" / slug
        plan_dir.mkdir(parents=True)
        (plan_dir / "task_plan.md").write_text(
            f"# {marker}\n### Phase 1\n**Status:** pending\n",
            encoding="utf-8",
        )
        (plan_dir / "progress.md").write_text(
            f"{marker}-PROGRESS\n", encoding="utf-8"
        )
        if active:
            (self.workspace / ".planning" / ".active_plan").write_text(
                f"{slug}\n", encoding="utf-8"
            )
        return plan_dir

    def run_hook(
        self,
        name: str,
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        assert POWERSHELL is not None
        return subprocess.run(
            [
                POWERSHELL,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(CURSOR_HOOKS / f"{name}.ps1"),
            ],
            cwd=str(cwd or self.workspace),
            env=env or self.clean_env(),
            text=True,
            encoding="utf-8-sig",
            capture_output=True,
            check=False,
            timeout=120,
        )

    def run_all_hooks(
        self, env: dict[str, str] | None = None
    ) -> dict[str, subprocess.CompletedProcess[str]]:
        return {
            name: self.run_hook(name, env=env)
            for name in (
                "pre-tool-use",
                "post-tool-use",
                "stop",
                "user-prompt-submit",
            )
        }

    def test_active_named_plan_reaches_all_native_hooks(self) -> None:
        marker = "NAMED-PLAN-MARKER"
        self.write_named_plan("plan-a", marker, active=True)

        results = self.run_all_hooks()

        for result in results.values():
            self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn(marker, results["pre-tool-use"].stdout)
        self.assertIn('"decision": "allow"', results["pre-tool-use"].stdout)
        self.assertIn("Update progress.md", results["post-tool-use"].stdout)
        self.assertIn(
            "Task incomplete (0/1 phases done)", results["stop"].stdout
        )
        self.assertIn(marker, results["user-prompt-submit"].stdout)
        self.assertIn(
            f"{marker}-PROGRESS", results["user-prompt-submit"].stdout
        )

    def test_legacy_root_still_reaches_all_native_hooks(self) -> None:
        self.write_root_plan()

        results = self.run_all_hooks()

        for result in results.values():
            self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("ROOT-PLAN-MARKER", results["pre-tool-use"].stdout)
        self.assertIn("Update progress.md", results["post-tool-use"].stdout)
        self.assertIn(
            "Task incomplete (0/1 phases done)", results["stop"].stdout
        )
        self.assertIn("ROOT-PLAN-MARKER", results["user-prompt-submit"].stdout)

    def test_plan_id_overrides_the_shared_active_pointer(self) -> None:
        self.write_named_plan("plan-a", "ACTIVE-PLAN-MARKER", active=True)
        self.write_named_plan("plan-b", "PINNED-PLAN-MARKER")

        result = self.run_hook(
            "user-prompt-submit",
            env=self.clean_env(PLAN_ID="plan-b"),
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("PINNED-PLAN-MARKER", result.stdout)
        self.assertNotIn("ACTIVE-PLAN-MARKER", result.stdout)

    def test_invalid_plan_id_fails_closed_across_hooks(self) -> None:
        self.write_root_plan()
        self.write_named_plan("plan-a", "ACTIVE-PLAN-MARKER", active=True)
        env = self.clean_env(PLAN_ID="missing-plan")

        results = self.run_all_hooks(env)

        for result in results.values():
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertNotIn("ROOT-PLAN-MARKER", result.stdout)
            self.assertNotIn("ACTIVE-PLAN-MARKER", result.stdout)
        self.assertIn('"decision": "allow"', results["pre-tool-use"].stdout)
        self.assertEqual("", results["post-tool-use"].stdout.strip())
        self.assertEqual("", results["stop"].stdout.strip())
        self.assertIn("PLAN_ID", results["user-prompt-submit"].stdout)
        self.assertIn("nothing injected", results["user-prompt-submit"].stdout)

    def test_multiple_named_plans_require_an_explicit_plan_id(self) -> None:
        self.write_named_plan("plan-a", "PLAN-A-MARKER")
        self.write_named_plan("plan-b", "PLAN-B-MARKER")

        result = self.run_hook("user-prompt-submit")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("Multiple plans are available", result.stdout)
        self.assertNotIn("PLAN-A-MARKER", result.stdout)
        self.assertNotIn("PLAN-B-MARKER", result.stdout)

    def test_plan_root_pin_resolves_a_nested_named_plan(self) -> None:
        parent = self.workspace
        project = parent / "project"
        project.mkdir()
        self.workspace = project
        self.write_named_plan("plan-a", "NESTED-NAMED-MARKER", active=True)
        self.workspace = parent
        self.write_root_plan("PARENT-ROOT-MARKER")

        result = self.run_hook(
            "user-prompt-submit",
            cwd=parent,
            env=self.clean_env(PWF_PLAN_ROOT=str(project)),
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("NESTED-NAMED-MARKER", result.stdout)
        self.assertNotIn("PARENT-ROOT-MARKER", result.stdout)


if __name__ == "__main__":
    unittest.main()
