"""Tests for scripts/resolve-plan-dir.sh — addresses #148.

Resolver order:
  1. $PLAN_ID env → .planning/<id>/ if exists
  2. .planning/.active_plan content → .planning/<id>/ if exists
  3. Newest .planning/<dir>/ by mtime
  4. Legacy fallback: <cwd>/task_plan.md exists → emit empty (caller uses cwd)
  5. Otherwise empty stdout, exit 0
"""
from __future__ import annotations

import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RESOLVE_SH = REPO_ROOT / "scripts" / "resolve-plan-dir.sh"


class ResolvePlanDirTests(unittest.TestCase):
    def run_resolver(self, cwd: Path, plan_id: str | None = None) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env.pop("PLAN_ID", None)
        if plan_id is not None:
            env["PLAN_ID"] = plan_id
        return subprocess.run(
            ["sh", str(RESOLVE_SH)],
            cwd=str(cwd),
            text=True,
            encoding="utf-8",
            capture_output=True,
            env=env,
            check=False,
        )

    def test_resolver_script_exists(self) -> None:
        self.assertTrue(RESOLVE_SH.exists(), "scripts/resolve-plan-dir.sh missing")

    def test_empty_repo_returns_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_resolver(Path(tmp))
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual("", result.stdout.strip())

    def test_env_plan_id_takes_precedence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".planning" / "alpha").mkdir(parents=True)
            (root / ".planning" / "beta").mkdir(parents=True)
            (root / ".planning" / ".active_plan").write_text("beta\n", encoding="utf-8")
            result = self.run_resolver(root, plan_id="alpha")
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue(result.stdout.strip().endswith("alpha"))

    def test_active_plan_used_when_env_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".planning" / "alpha").mkdir(parents=True)
            (root / ".planning" / "beta").mkdir(parents=True)
            (root / ".planning" / ".active_plan").write_text("beta\n", encoding="utf-8")
            result = self.run_resolver(root)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue(result.stdout.strip().endswith("beta"))

    def test_falls_back_to_newest_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old = root / ".planning" / "older"
            new = root / ".planning" / "newer"
            old.mkdir(parents=True)
            (old / "task_plan.md").write_text("# old\n", encoding="utf-8")
            time.sleep(0.05)
            new.mkdir(parents=True)
            (new / "task_plan.md").write_text("# new\n", encoding="utf-8")
            # bump mtime explicitly to be safe across filesystems
            os.utime(new, None)
            result = self.run_resolver(root)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue(
                result.stdout.strip().endswith("newer"),
                f"expected newer, got {result.stdout!r}",
            )

    def test_legacy_root_plan_emits_empty(self) -> None:
        # When no .planning/ but cwd/task_plan.md exists, resolver emits empty so
        # callers fall back to the legacy root path. This preserves v1.x users.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "task_plan.md").write_text("# legacy\n", encoding="utf-8")
            result = self.run_resolver(root)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual("", result.stdout.strip())

    def test_env_plan_id_pointing_to_missing_dir_falls_through(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            real = root / ".planning" / "real"
            real.mkdir(parents=True)
            (real / "task_plan.md").write_text("# real plan\n", encoding="utf-8")
            result = self.run_resolver(root, plan_id="ghost")
            self.assertEqual(0, result.returncode, result.stderr)
            # Should fall through to newest existing plan dir
            self.assertTrue(result.stdout.strip().endswith("real"))

    def test_corrupt_active_plan_whitespace_only_falls_through(self) -> None:
        # Regression for v2.40: .active_plan filled with whitespace/newlines
        # used to be normalized to an empty string by `tr -d`, leaving the
        # resolver about to look up `.planning//task_plan.md`. The slug-validity
        # check now rejects empty / whitespace-only content and falls through to
        # the newest-mtime resolution path.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            real = root / ".planning" / "real"
            real.mkdir(parents=True)
            (real / "task_plan.md").write_text("# real plan\n", encoding="utf-8")
            (root / ".planning" / ".active_plan").write_text("   \n\n   \n", encoding="utf-8")
            result = self.run_resolver(root)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue(
                result.stdout.strip().endswith("real"),
                f"expected fall-through to real, got {result.stdout!r}",
            )

    def test_corrupt_active_plan_with_path_separator_rejected(self) -> None:
        # Regression for v2.40: a malicious or corrupt .active_plan containing
        # a path separator (e.g. ../escape, ./.planning/foo) used to be passed
        # directly to the candidate path, opening a path-traversal-shaped
        # surface. The slug-validity check now rejects any plan-id with `/`,
        # `..`, or leading-dot, falling through to newest-mtime.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            real = root / ".planning" / "real"
            real.mkdir(parents=True)
            (real / "task_plan.md").write_text("# real plan\n", encoding="utf-8")
            (root / ".planning" / ".active_plan").write_text("../escape\n", encoding="utf-8")
            result = self.run_resolver(root)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue(
                result.stdout.strip().endswith("real"),
                f"expected fall-through to real, got {result.stdout!r}",
            )

    def test_env_plan_id_with_whitespace_rejected(self) -> None:
        # Regression for v2.40: PLAN_ID env with whitespace or empty value must
        # not bypass the slug check. Falls through cleanly.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            real = root / ".planning" / "real"
            real.mkdir(parents=True)
            (real / "task_plan.md").write_text("# real plan\n", encoding="utf-8")
            result = self.run_resolver(root, plan_id="   ")
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue(result.stdout.strip().endswith("real"))

    def test_latest_dir_scan_skips_invalid_slug_names(self) -> None:
        # Regression for v2.40: dirs with non-safe names (path traversal,
        # dotfiles, leading whitespace) must be skipped by the newest-mtime
        # scan so a malicious .planning/..foo/ cannot win the resolution.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            good = root / ".planning" / "good"
            good.mkdir(parents=True)
            (good / "task_plan.md").write_text("# good\n", encoding="utf-8")
            # A dot-prefixed dir; should be skipped by both the slug check
            # AND the case .*) continue ;; guard.
            sneaky = root / ".planning" / ".sneaky"
            sneaky.mkdir(parents=True)
            (sneaky / "task_plan.md").write_text("# sneaky\n", encoding="utf-8")
            result = self.run_resolver(root)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue(
                result.stdout.strip().endswith("good"),
                f"expected good, got {result.stdout!r}",
            )

    def test_dead_active_plan_target_falls_through(self) -> None:
        # Regression for v2.40: .active_plan points to a dir that has been
        # deleted. Resolver must fall through to newest-existing instead of
        # printing the dead path.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            real = root / ".planning" / "real"
            real.mkdir(parents=True)
            (real / "task_plan.md").write_text("# real\n", encoding="utf-8")
            (root / ".planning" / ".active_plan").write_text("deleted-plan\n", encoding="utf-8")
            # Note: .planning/deleted-plan/ never created
            result = self.run_resolver(root)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue(
                result.stdout.strip().endswith("real"),
                f"expected real, got {result.stdout!r}",
            )


if __name__ == "__main__":
    unittest.main()
