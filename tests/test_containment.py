"""Realpath-containment tests for scripts/resolve-plan-dir.sh (security A1.3, W1E).

A resolved plan dir must canonicalize to a path UNDER the project root (the CWD
the resolver runs from). A symlink inside a valid-looking slug dir that points
outside the workspace would otherwise let the hooks hash and inject an arbitrary
file. On a containment violation the resolver treats the candidate as unresolved
and falls through (to a contained sibling, or to empty stdout).

The escape case needs a REAL symlink that os.path.realpath sees leaving the root.
Many environments cannot create one (Windows without the symlink privilege, MSYS
without winsymlinks, restricted filesystems); there `os.symlink` raises or the
link is materialized in-place and never escapes. We probe that capability once
and skipif it is absent, per the existing skip patterns in this suite.

The positive case (normal dirs still resolve) always runs.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RESOLVE_SH = REPO_ROOT / "skills" / "planning-with-files" / "scripts" / "resolve-plan-dir.sh"


def have_sh() -> bool:
    return shutil.which("sh") is not None


def can_make_escaping_symlink() -> bool:
    """True only if we can create a dir symlink that realpath sees escaping root.

    Mirrors the script's containment check (os.path.realpath comparison) so the
    skip is honest: if a created link does not actually escape per realpath, the
    test could not exercise containment and must skip.
    """
    outside = tempfile.mkdtemp()
    root = tempfile.mkdtemp()
    try:
        target = os.path.join(outside, "realplan")
        os.makedirs(target)
        link = os.path.join(root, "link")
        try:
            os.symlink(target, link, target_is_directory=True)
        except (OSError, NotImplementedError, AttributeError):
            return False
        if not os.path.islink(link):
            return False
        root_real = os.path.realpath(root)
        cand_real = os.path.realpath(link)
        return not (
            cand_real == root_real or cand_real.startswith(root_real + os.sep)
        )
    finally:
        shutil.rmtree(outside, ignore_errors=True)
        shutil.rmtree(root, ignore_errors=True)


SYMLINK_OK = can_make_escaping_symlink()


@unittest.skipUnless(have_sh(), "sh not available on this platform")
class ContainmentTests(unittest.TestCase):
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

    def test_normal_dirs_still_resolve(self) -> None:
        # Sanity: a contained plan dir resolves normally (containment never
        # blocks legitimate paths). Always runs.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = root / ".planning" / "real"
            plan.mkdir(parents=True)
            (plan / "task_plan.md").write_text("# real\n", encoding="utf-8")
            (root / ".planning" / ".active_plan").write_text("real\n", encoding="utf-8")
            result = self.run_resolver(root)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue(
                result.stdout.strip().endswith("real"),
                f"contained dir must resolve, got {result.stdout!r}",
            )

    @unittest.skipUnless(SYMLINK_OK, "platform cannot create an escaping dir symlink")
    def test_active_plan_symlink_out_of_root_is_rejected(self) -> None:
        # .active_plan points at a slug whose dir is a symlink escaping the root.
        # The resolver must NOT emit that escaping path; it falls through to a
        # contained sibling (here, "safe").
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside:
            root = Path(tmp)
            (root / ".planning").mkdir()
            # a contained fallback dir
            safe = root / ".planning" / "safe"
            safe.mkdir()
            (safe / "task_plan.md").write_text("# safe\n", encoding="utf-8")
            # the escaping symlink target
            target = Path(outside) / "evil"
            target.mkdir()
            (target / "task_plan.md").write_text("# evil\n", encoding="utf-8")
            os.symlink(str(target), str(root / ".planning" / "escape"), target_is_directory=True)
            (root / ".planning" / ".active_plan").write_text("escape\n", encoding="utf-8")

            result = self.run_resolver(root)
            self.assertEqual(0, result.returncode, result.stderr)
            resolved = result.stdout.strip()
            self.assertFalse(
                resolved.endswith("escape"),
                f"escaping symlink dir must be rejected, got {resolved!r}",
            )
            # And the resolved path (if any) must stay under the root.
            if resolved:
                self.assertTrue(
                    os.path.realpath(resolved).startswith(os.path.realpath(str(root))),
                    f"resolved path escaped root: {resolved!r}",
                )

    @unittest.skipUnless(SYMLINK_OK, "platform cannot create an escaping dir symlink")
    def test_env_plan_id_symlink_out_of_root_is_rejected(self) -> None:
        # Same containment guard via the $PLAN_ID resolution path, with no
        # contained sibling: the resolver must emit empty (caller falls back to
        # the legacy root path) rather than the escaping dir.
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside:
            root = Path(tmp)
            (root / ".planning").mkdir()
            target = Path(outside) / "evil"
            target.mkdir()
            (target / "task_plan.md").write_text("# evil\n", encoding="utf-8")
            os.symlink(str(target), str(root / ".planning" / "escape"), target_is_directory=True)

            result = self.run_resolver(root, plan_id="escape")
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(
                "",
                result.stdout.strip(),
                "escaping symlink via PLAN_ID must yield empty (legacy fallback)",
            )


if __name__ == "__main__":
    unittest.main()
