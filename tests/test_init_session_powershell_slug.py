"""Windows PowerShell parity tests for slug-aware init-session.ps1."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
import os
from datetime import date
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INIT_PS1 = REPO_ROOT / "scripts" / "init-session.ps1"
POWERSHELL = shutil.which("powershell") or shutil.which("powershell.exe")


@unittest.skipUnless(POWERSHELL, "requires Windows PowerShell")
class InitSessionPowerShellSlugTests(unittest.TestCase):
    def run_init(self, cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                POWERSHELL,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(INIT_PS1),
                *args,
            ],
            cwd=str(cwd),
            text=True,
            encoding="utf-8-sig",
            capture_output=True,
            check=False,
        )

    def test_named_plan_creates_dated_slug_directory_and_active_pointer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self.run_init(root, "Backend Refactor")
            self.assertEqual(0, result.returncode, result.stderr)

            plan_id = f"{date.today().isoformat()}-backend-refactor"
            plan_dir = root / ".planning" / plan_id
            self.assertTrue((plan_dir / "task_plan.md").is_file())
            self.assertTrue((plan_dir / "findings.md").is_file())
            self.assertTrue((plan_dir / "progress.md").is_file())
            self.assertFalse((root / "task_plan.md").exists())
            active = (root / ".planning" / ".active_plan").read_text(encoding="utf-8-sig").strip()
            self.assertEqual(plan_id, active)

    def test_zero_args_preserves_legacy_root_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self.run_init(root)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue((root / "task_plan.md").is_file())
            self.assertTrue((root / "findings.md").is_file())
            self.assertTrue((root / "progress.md").is_file())
            self.assertFalse((root / ".planning").exists())
            self.assertIn("Created task_plan.md", result.stdout)
            self.assertIn("Created findings.md", result.stdout)
            self.assertIn("Created progress.md", result.stdout)

    def test_plan_dir_without_name_uses_untitled_slug(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self.run_init(root, "-PlanDir")
            self.assertEqual(0, result.returncode, result.stderr)
            dirs = [p for p in (root / ".planning").iterdir() if p.is_dir()]
            self.assertEqual(1, len(dirs))
            self.assertRegex(
                dirs[0].name,
                rf"^{date.today().isoformat()}-untitled-[a-f0-9]{{8}}$",
            )

    def test_slug_sanitizes_unsafe_characters(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self.run_init(root, "Foo / Bar! Baz??")
            self.assertEqual(0, result.returncode, result.stderr)
            expected = root / ".planning" / f"{date.today().isoformat()}-foo-bar-baz"
            self.assertTrue(expected.is_dir())

    def test_slug_collision_appends_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = self.run_init(root, "same name")
            second = self.run_init(root, "same name")
            self.assertEqual(0, first.returncode, first.stderr)
            self.assertEqual(0, second.returncode, second.stderr)
            today = date.today().isoformat()
            self.assertTrue((root / ".planning" / f"{today}-same-name").is_dir())
            self.assertTrue((root / ".planning" / f"{today}-same-name-2").is_dir())

    def test_slug_plan_inherits_root_gated_mode_and_is_attested(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".mode").write_text("autonomous gate\n", encoding="ascii")
            result = self.run_init(root, "Child Plan")
            self.assertEqual(0, result.returncode, result.stderr)
            plan_dir = root / ".planning" / f"{date.today().isoformat()}-child-plan"
            self.assertEqual(
                "autonomous gate",
                (plan_dir / ".mode").read_text(encoding="ascii").strip(),
            )
            self.assertEqual("0", (plan_dir / ".stop_blocks").read_text(encoding="ascii").strip())
            self.assertRegex((plan_dir / ".nonce").read_text(encoding="ascii"), r"^[a-f0-9]{16}$")
            self.assertTrue((plan_dir / ".attestation").is_file())

    def test_named_plan_preserves_template_selection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self.run_init(root, "-Template", "analytics", "Analytics Run")
            self.assertEqual(0, result.returncode, result.stderr)
            plan_dir = root / ".planning" / f"{date.today().isoformat()}-analytics-run"
            expected = (REPO_ROOT / "templates" / "analytics_task_plan.md").read_bytes()
            self.assertEqual(expected, (plan_dir / "task_plan.md").read_bytes())

    def test_named_autonomous_plan_writes_mode_and_attestation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self.run_init(root, "-Autonomous", "Auto Plan")
            self.assertEqual(0, result.returncode, result.stderr)
            plan_dir = root / ".planning" / f"{date.today().isoformat()}-auto-plan"
            self.assertEqual(
                "autonomous",
                (plan_dir / ".mode").read_text(encoding="ascii").strip(),
            )
            self.assertTrue((plan_dir / ".attestation").is_file())

    def test_named_autonomous_plan_attests_new_plan_despite_stale_plan_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            previous = os.environ.get("PLAN_ID")
            os.environ["PLAN_ID"] = "stale-plan-id"
            try:
                result = self.run_init(root, "-Autonomous", "Bound Plan")
            finally:
                if previous is None:
                    os.environ.pop("PLAN_ID", None)
                else:
                    os.environ["PLAN_ID"] = previous

            self.assertEqual(0, result.returncode, result.stderr)
            plan_dir = root / ".planning" / f"{date.today().isoformat()}-bound-plan"
            self.assertTrue((plan_dir / ".attestation").is_file())


if __name__ == "__main__":
    unittest.main()
