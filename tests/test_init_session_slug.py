"""Tests for slug-aware init-session.sh — addresses #148.

Backward-compat behavior:
  - Zero args → legacy root mode: writes task_plan.md/findings.md/progress.md in cwd
  - One+ string args → slug mode: writes under .planning/YYYY-MM-DD-<slug>/
  - --plan-dir flag forces slug mode without naming
  - Slug collisions append -2, -3, ...
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
INIT_SH = REPO_ROOT / "scripts" / "init-session.sh"


class InitSessionSlugTests(unittest.TestCase):
    def run_init(self, cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["sh", str(INIT_SH), *args],
            cwd=str(cwd),
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
        )

    def test_legacy_zero_args_keeps_root_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self.run_init(root)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue((root / "task_plan.md").exists())
            self.assertTrue((root / "findings.md").exists())
            self.assertTrue((root / "progress.md").exists())
            self.assertFalse((root / ".planning").exists(), "legacy mode must not create .planning/")

    def test_slug_arg_creates_dated_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self.run_init(root, "Backend Refactor")
            self.assertEqual(0, result.returncode, result.stderr)
            today = date.today().isoformat()
            expected = root / ".planning" / f"{today}-backend-refactor"
            self.assertTrue(expected.is_dir(), f"missing {expected}")
            self.assertTrue((expected / "task_plan.md").exists())
            self.assertTrue((expected / "findings.md").exists())
            self.assertTrue((expected / "progress.md").exists())
            active = (root / ".planning" / ".active_plan").read_text(encoding="utf-8").strip()
            self.assertEqual(active, f"{today}-backend-refactor")

    def test_slug_sanitizes_unsafe_chars(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self.run_init(root, "Foo / Bar! Baz??")
            self.assertEqual(0, result.returncode, result.stderr)
            today = date.today().isoformat()
            expected = root / ".planning" / f"{today}-foo-bar-baz"
            self.assertTrue(expected.is_dir(), f"got {[p.name for p in (root / '.planning').iterdir()]}")

    def test_slug_collision_appends_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_init(root, "same name")
            result = self.run_init(root, "same name")
            self.assertEqual(0, result.returncode, result.stderr)
            today = date.today().isoformat()
            self.assertTrue((root / ".planning" / f"{today}-same-name").is_dir())
            self.assertTrue((root / ".planning" / f"{today}-same-name-2").is_dir())

    def test_plan_dir_flag_default_slug(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self.run_init(root, "--plan-dir")
            self.assertEqual(0, result.returncode, result.stderr)
            today = date.today().isoformat()
            dirs = list((root / ".planning").iterdir())
            dirs = [d for d in dirs if d.is_dir()]
            self.assertEqual(1, len(dirs))
            self.assertTrue(re.match(rf"^{today}-untitled-[a-z0-9]+$", dirs[0].name))

    def test_help_flags_print_usage_without_mutating_planning_state(self) -> None:
        for flag in ("-h", "--help"):
            with self.subTest(flag=flag), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                result = self.run_init(root, flag)
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertIn("Usage:", result.stdout)
                self.assertEqual([], list(root.iterdir()))

    def test_template_flag_still_works_in_legacy_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self.run_init(root, "--template", "default")
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue((root / "task_plan.md").exists())
            self.assertFalse((root / ".planning").exists())

    def test_slug_init_replaces_hardlinked_pointer_without_mutating_peer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            planning = root / ".planning"
            planning.mkdir()
            sentinel = root / "sentinel.txt"
            sentinel.write_bytes(b"KEEP-ME")
            pointer = planning / ".active_plan"
            os.link(sentinel, pointer)

            result = self.run_init(root, "Hardlink Test")

            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertEqual(b"KEEP-ME", sentinel.read_bytes())
            expected = f"{date.today().isoformat()}-hardlink-test"
            self.assertEqual(expected, pointer.read_text(encoding="utf-8").strip())

    def test_slug_init_rejects_symlink_pointer_without_following_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            planning = root / ".planning"
            planning.mkdir()
            sentinel = root / "sentinel.txt"
            sentinel.write_bytes(b"KEEP-ME")
            pointer = planning / ".active_plan"
            try:
                pointer.symlink_to(sentinel)
            except (OSError, NotImplementedError) as error:
                self.skipTest(f"file symlinks unavailable: {error}")

            result = self.run_init(root, "Symlink Test")

            self.assertNotEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertEqual(b"KEEP-ME", sentinel.read_bytes())
            self.assertTrue(pointer.is_symlink())
            self.assertIn("active plan pointer", result.stderr)

    def test_slug_init_rejects_external_planning_directory_before_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside_tmp:
            root = Path(tmp)
            outside = Path(outside_tmp)
            planning = root / ".planning"
            try:
                planning.symlink_to(outside, target_is_directory=True)
            except (OSError, NotImplementedError) as error:
                if os.name != "nt":
                    self.skipTest(f"directory symlinks unavailable: {error}")
                junction = subprocess.run(
                    ["cmd.exe", "/d", "/c", "mklink", "/J", str(planning), str(outside)],
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    capture_output=True,
                    check=False,
                )
                if junction.returncode != 0:
                    self.skipTest(
                        f"directory links unavailable: {error}; {junction.stdout}{junction.stderr}"
                    )

            result = self.run_init(root, "Escaped Plan")

            self.assertNotEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertEqual([], list(outside.iterdir()))
            self.assertIn("outside the project", result.stderr)

if __name__ == "__main__":
    unittest.main()
