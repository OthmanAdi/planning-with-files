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


def host_realpath(sh_path: str) -> str:
    """Canonicalize a path emitted by an sh script for host-side comparison.

    Under Git Bash on Windows the resolver prints POSIX-style paths, and the
    user temp directory is mounted at /tmp, so os.path.realpath on the raw
    string would resolve against a nonexistent C:\\tmp and the containment
    assertion would fail even though the resolved dir is contained. Map the
    path back to its Windows form with cygpath first, then canonicalize.
    """
    if os.name == "nt" and sh_path.startswith("/"):
        cygpath = shutil.which("cygpath")
        if cygpath:
            mapped = subprocess.run(
                [cygpath, "-w", sh_path],
                text=True,
                capture_output=True,
                check=False,
            ).stdout.strip()
            if mapped:
                sh_path = mapped
    return os.path.realpath(sh_path)


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
            # And the resolved path (if any) must stay under the root. Compare
            # both sides in the host path domain: the resolver's stdout is a
            # POSIX-style path under Git Bash (see host_realpath).
            if resolved:
                self.assertTrue(
                    host_realpath(resolved).startswith(os.path.realpath(str(root))),
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


INJECT_SH = REPO_ROOT / "skills" / "planning-with-files" / "scripts" / "inject-plan.sh"


@unittest.skipUnless(have_sh(), "sh not available on this platform")
class WindowsNativeCanonicalizerTests(unittest.TestCase):
    """Regression: a Windows-native coreutils realpath (e.g. an installed
    C:\\Program Files\\coreutils on PATH ahead of Git's usr/bin) canonicalizes
    MSYS-style /c/... input to C:\\-style BACKSLASH output. The containment
    prefix match in is_within_root is written with forward slashes, so every
    canonical pair mismatched: the resolver (fail-closed) resolved nothing and
    inject-plan.sh (guarded exit) emitted nothing — plan resolution and hook
    injection silently dark on the whole machine. Found live 2026-07-18.

    A PATH-prepended stub realpath reproduces the backslash output shape on
    every platform, so this guards the norm_slashes fix on Linux CI too.
    """

    def make_backslash_realpath(self, bin_dir: Path) -> None:
        stub = bin_dir / "realpath"
        stub.write_text(
            "#!/bin/sh\n"
            "# test stub: Windows-native realpath shape (backslash separators)\n"
            'case "$1" in\n'
            '  "") exit 1 ;;\n'
            '  /*) abs="$1" ;;\n'
            '  .) abs="$(pwd -P)" ;;\n'
            '  *) abs="$(pwd -P)/$1" ;;\n'
            "esac\n"
            "printf '%s\\n' \"$abs\" | sed 's|/|\\\\|g'\n",
            encoding="utf-8",
            newline="\n",
        )
        os.chmod(stub, 0o755)

    def run_with_stub(self, script: Path, cwd: Path) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as stub_tmp:
            bin_dir = Path(stub_tmp) / "bin"
            bin_dir.mkdir()
            self.make_backslash_realpath(bin_dir)
            env = os.environ.copy()
            env.pop("PLAN_ID", None)
            env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
            return subprocess.run(
                ["sh", str(script)],
                cwd=str(cwd),
                text=True,
                encoding="utf-8",
                capture_output=True,
                env=env,
                check=False,
            )

    def test_resolver_survives_backslash_realpath(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = root / ".planning" / "real"
            plan.mkdir(parents=True)
            (plan / "task_plan.md").write_text("# real\n", encoding="utf-8")
            (root / ".planning" / ".active_plan").write_text("real\n", encoding="utf-8")
            result = self.run_with_stub(RESOLVE_SH, root)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue(
                result.stdout.strip().endswith("real"),
                f"backslash canonical paths must not kill resolution, got {result.stdout!r}",
            )

    def test_inject_survives_backslash_realpath(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = root / ".planning" / "real"
            plan.mkdir(parents=True)
            (plan / "task_plan.md").write_text("# real plan body\n", encoding="utf-8")
            (root / ".planning" / ".active_plan").write_text("real\n", encoding="utf-8")
            result = self.run_with_stub(INJECT_SH, root)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn(
                "===BEGIN-PWF-DATA kind=plan nonce=",
                result.stdout,
                f"injection must survive backslash canonical paths, got {result.stdout!r}",
            )
            self.assertIn("# real plan body", result.stdout)


@unittest.skipIf(os.name == "nt", "native POSIX PATH containment contract")
@unittest.skipUnless(have_sh(), "sh not available on this platform")
class InjectorInterpreterContainmentTests(unittest.TestCase):
    def make_python_canaries(self, root: Path, marker: Path) -> Path:
        bin_dir = root / "fake-bin"
        bin_dir.mkdir()
        for name in ("python3", "python"):
            candidate = bin_dir / name
            candidate.write_text(
                "#!/bin/sh\n"
                f"printf touched > '{marker.as_posix()}'\n"
                "exit 1\n",
                encoding="utf-8",
                newline="\n",
            )
            candidate.chmod(0o755)
        return bin_dir

    def run_with_canaries(
        self, root: Path, bin_dir: Path
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        for name in ("PWF_TRUSTED_PYTHON", "PYTHON_BIN", "PLAN_ID"):
            env.pop(name, None)
        env["PATH"] = os.pathsep.join((str(bin_dir), env.get("PATH", "")))
        return subprocess.run(
            ["sh", str(INJECT_SH)],
            cwd=str(root),
            text=True,
            encoding="utf-8",
            capture_output=True,
            env=env,
            check=False,
        )

    def test_no_plan_does_not_execute_path_python(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            marker = root / "path-python-executed"
            bin_dir = self.make_python_canaries(root, marker)

            result = self.run_with_canaries(root, bin_dir)

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual("", result.stdout)
            self.assertFalse(marker.exists())

    @unittest.skipUnless(SYMLINK_OK, "platform cannot create an escaping dir symlink")
    def test_escaping_plan_does_not_execute_path_python(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside:
            root = Path(tmp)
            planning = root / ".planning"
            planning.mkdir()
            target = Path(outside) / "escape"
            target.mkdir()
            (target / "task_plan.md").write_text("# outside\n", encoding="utf-8")
            os.symlink(target, planning / "escape", target_is_directory=True)
            (planning / ".active_plan").write_text("escape\n", encoding="utf-8")
            marker = root / "path-python-executed"
            bin_dir = self.make_python_canaries(root, marker)

            result = self.run_with_canaries(root, bin_dir)

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual("", result.stdout)
            self.assertFalse(
                marker.exists(),
                "PATH Python must remain unexecuted until containment succeeds",
            )

    @unittest.skipUnless(SYMLINK_OK, "platform cannot create an escaping dir symlink")
    def test_escaping_planning_root_stays_silent_and_does_not_execute_path_python(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside:
            root = Path(tmp)
            outside_planning = Path(outside) / ".planning"
            outside_plan = outside_planning / "escape"
            outside_plan.mkdir(parents=True)
            (outside_plan / "task_plan.md").write_text("# outside\n", encoding="utf-8")
            (outside_planning / ".active_plan").write_text("escape\n", encoding="utf-8")
            os.symlink(outside_planning, root / ".planning", target_is_directory=True)
            marker = root / "path-python-executed"
            bin_dir = self.make_python_canaries(root, marker)

            result = self.run_with_canaries(root, bin_dir)

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual("", result.stdout)
            self.assertFalse(
                marker.exists(),
                "PATH Python must remain unexecuted on precheck containment escape",
            )


if __name__ == "__main__":
    unittest.main()
