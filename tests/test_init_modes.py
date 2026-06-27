"""Tests for v3 opt-in modes in init-session.sh (architecture C1 / C2 / C7).

  * --autonomous writes <plan-dir>/.mode = "autonomous", a 16-hex .nonce for
    delimiter framing, resets .stop_blocks to 0, and auto-attests the plan
    (attestation default-on, security rec 1) so .attestation exists.
  * --gated writes "autonomous gate" (gated implies autonomous).
  * A no-flag run is byte-equivalent to v2.43: it creates the three planning
    files and NO .mode / .nonce / .attestation marker. The legacy invariant.

The v3 mode side effects (auto-attest) need attest-plan.sh as a sibling; that is
present under skills/planning-with-files/scripts/, so we invoke init-session.sh
from there.
"""
from __future__ import annotations

import os
import re
import subprocess
import tempfile
import unittest
from datetime import date
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "skills" / "planning-with-files" / "scripts"
INIT_SH = SCRIPTS_DIR / "init-session.sh"


class InitModesTestBase(unittest.TestCase):
    def run_init(self, cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env.pop("PLAN_ID", None)
        return subprocess.run(
            ["sh", str(INIT_SH), *args],
            cwd=str(cwd),
            text=True,
            encoding="utf-8",
            capture_output=True,
            env=env,
            check=False,
        )

    def only_plan_dir(self, root: Path) -> Path:
        dirs = [d for d in (root / ".planning").iterdir() if d.is_dir()]
        self.assertEqual(1, len(dirs), f"expected one plan dir, got {[d.name for d in dirs]}")
        return dirs[0]


class AutonomousModeTests(InitModesTestBase):
    def test_autonomous_writes_mode_nonce_and_attestation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self.run_init(root, "--autonomous", "Long Run")
            self.assertEqual(0, result.returncode, result.stderr)
            plan_dir = self.only_plan_dir(root)

            mode = (plan_dir / ".mode").read_text(encoding="utf-8").strip()
            self.assertEqual("autonomous", mode)

            nonce = (plan_dir / ".nonce").read_text(encoding="utf-8").strip()
            self.assertRegex(nonce, r"^[0-9a-f]{16}$", f"nonce not 16 hex chars: {nonce!r}")

            self.assertTrue(
                (plan_dir / ".attestation").exists(),
                "autonomous mode must auto-attest (attestation default-on)",
            )
            attest = (plan_dir / ".attestation").read_text(encoding="utf-8").strip()
            self.assertRegex(attest, r"^[0-9a-f]{64}$", "attestation must be a sha256 hex digest")

    def test_autonomous_resets_stop_blocks_to_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_init(root, "--autonomous", "Run")
            plan_dir = self.only_plan_dir(root)
            blocks = (plan_dir / ".stop_blocks").read_text(encoding="utf-8").strip()
            self.assertEqual("0", blocks)


class GatedModeTests(InitModesTestBase):
    def test_gated_writes_autonomous_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self.run_init(root, "--gated", "Build Pipeline")
            self.assertEqual(0, result.returncode, result.stderr)
            plan_dir = self.only_plan_dir(root)
            mode = (plan_dir / ".mode").read_text(encoding="utf-8").strip()
            # gated implies autonomous, so the marker carries both tokens.
            self.assertEqual("autonomous gate", mode)
            self.assertIn("gate", mode)

    def test_gated_also_resets_stop_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_init(root, "--gated", "Pipeline")
            plan_dir = self.only_plan_dir(root)
            self.assertEqual("0", (plan_dir / ".stop_blocks").read_text(encoding="utf-8").strip())


class LegacyInvariantTests(InitModesTestBase):
    def test_no_flag_creates_no_v3_markers(self) -> None:
        # The legacy invariant: a no-flag run is byte-equivalent to v2.43. It
        # writes the three planning files at root and NONE of the v3 markers.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self.run_init(root)
            self.assertEqual(0, result.returncode, result.stderr)
            # v2 expectations (mirrors test_init_session_slug.py legacy test).
            self.assertTrue((root / "task_plan.md").exists())
            self.assertTrue((root / "findings.md").exists())
            self.assertTrue((root / "progress.md").exists())
            self.assertFalse((root / ".planning").exists(), "legacy mode must not create .planning/")
            # No v3 markers anywhere.
            self.assertFalse((root / ".mode").exists(), "no-flag run must not write .mode")
            self.assertFalse((root / ".nonce").exists(), "no-flag run must not write .nonce")
            self.assertFalse(
                (root / ".attestation").exists() or (root / ".plan-attestation").exists(),
                "no-flag run must not auto-attest (attestation stays opt-in in legacy mode)",
            )
            self.assertFalse((root / ".stop_blocks").exists(), "no-flag run must not write .stop_blocks")

    def test_slug_no_flag_creates_no_v3_markers(self) -> None:
        # Same invariant for the slug (named) path without a v3 flag.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self.run_init(root, "Backend Refactor")
            self.assertEqual(0, result.returncode, result.stderr)
            today = date.today().isoformat()
            plan_dir = root / ".planning" / f"{today}-backend-refactor"
            self.assertTrue(plan_dir.is_dir())
            self.assertFalse((plan_dir / ".mode").exists())
            self.assertFalse((plan_dir / ".nonce").exists())
            self.assertFalse((plan_dir / ".attestation").exists())
            self.assertFalse((plan_dir / ".stop_blocks").exists())


class AutonomousLegacyRootModeTests(InitModesTestBase):
    def test_autonomous_in_legacy_root_writes_dotfiles_at_root(self) -> None:
        # v3 flags also work in legacy root mode: dotfiles land at the project
        # root next to task_plan.md, no .planning/ dir.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self.run_init(root, "--autonomous")
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertFalse((root / ".planning").exists())
            self.assertEqual("autonomous", (root / ".mode").read_text(encoding="utf-8").strip())
            self.assertRegex(
                (root / ".nonce").read_text(encoding="utf-8").strip(), r"^[0-9a-f]{16}$"
            )
            self.assertEqual("0", (root / ".stop_blocks").read_text(encoding="utf-8").strip())


if __name__ == "__main__":
    unittest.main()
