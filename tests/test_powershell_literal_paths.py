"""Literal-path and Windows PowerShell 5.1 coverage for the shared PowerShell
helpers (follow-up to PR #251).

Two silent-death shapes found by the v3.20.0 review:

* ``resolve-plan-dir.ps1`` tested candidate directories with wildcard-
  interpreting ``Test-Path`` and listed ``.planning`` with ``Get-ChildItem
  -Path``. In a project path containing ``[`` or ``]`` those calls match
  nothing, so a valid ``.active_plan`` pointer, and even an explicit
  ``PLAN_ID``, resolved to an empty result and every PowerShell hook route
  injected nothing. ``-LiteralPath`` throughout restores the selection.
* ``attest-plan.ps1`` validated ``PWF_PLAN_ROOT`` with
  ``[IO.Path]::IsPathFullyQualified``, which .NET Framework does not have, so
  Windows PowerShell 5.1 aborted the attester whenever the pin was set. The
  same drive-qualified regex that PR #251 gave the resolver applies.

The bracket case runs under pwsh only: Windows PowerShell 5.1 relocates the
process cwd to $PSHOME when the inherited directory contains wildcard
characters (issue #256), which is a different problem with its own issue.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "skills" / "planning-with-files" / "scripts"
PWSH = shutil.which("pwsh")
WINDOWS_POWERSHELL = shutil.which("powershell.exe") if os.name == "nt" else None
SCRUB_VARS = ("PLAN_ID", "PWF_PLAN_ROOT", "PLANNING_DISABLED")


def clean_env(**extra: str) -> dict[str, str]:
    env = os.environ.copy()
    for name in SCRUB_VARS:
        env.pop(name, None)
    env.update(extra)
    return env


def run_script(exe: str, script: Path, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    # Set-Location -LiteralPath keeps a bracketed cwd intact; -File would let
    # the host expand it as a wildcard pattern.
    command = f"Set-Location -LiteralPath '{cwd}'; & '{script}'; exit $LASTEXITCODE"
    return subprocess.run(
        [exe, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
        cwd=str(cwd),
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
        timeout=120,
    )


def write_plan(plan_dir: Path, marker: str) -> None:
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "task_plan.md").write_bytes(
        f"# {marker}\n### Phase 1\n**Status:** in_progress\n".encode("utf-8")
    )


@unittest.skipUnless(PWSH, "requires pwsh")
class ResolverLiteralPathTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="pwf-literal-")
        # The wildcard characters live in the project path itself.
        self.project = Path(self._tmp.name) / "proj [v2]"
        self.project.mkdir()
        write_plan(self.project / ".planning" / "plan-a", "PLAN-A")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def resolve(self, env: dict[str, str]) -> str:
        assert PWSH is not None
        result = run_script(PWSH, SCRIPTS / "resolve-plan-dir.ps1", self.project, env)
        self.assertEqual(0, result.returncode, result.stderr)
        return result.stdout.strip()

    def test_active_pointer_resolves_in_a_bracketed_project_path(self) -> None:
        (self.project / ".planning" / ".active_plan").write_bytes(b"plan-a\n")
        resolved = self.resolve(clean_env())
        self.assertTrue(resolved.endswith("plan-a"), resolved)

    def test_plan_id_resolves_in_a_bracketed_project_path(self) -> None:
        resolved = self.resolve(clean_env(PLAN_ID="plan-a"))
        self.assertTrue(resolved.endswith("plan-a"), resolved)

    def test_newest_plan_fallback_resolves_in_a_bracketed_project_path(self) -> None:
        resolved = self.resolve(clean_env())
        self.assertTrue(resolved.endswith("plan-a"), resolved)


class AttesterPinContract:
    """Shared pin assertions; concrete classes pick the interpreter."""

    exe: str | None = None

    def setUp(self) -> None:  # noqa: N802 (unittest naming)
        self._tmp = tempfile.TemporaryDirectory(prefix="pwf-attest-pin-")
        self.parent = Path(self._tmp.name)
        self.project = self.parent / "project"
        write_plan(self.project / ".planning" / "plan-a", "PINNED")

    def tearDown(self) -> None:  # noqa: N802 (unittest naming)
        self._tmp.cleanup()

    def attest(self, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
        assert self.exe is not None
        return run_script(self.exe, SCRIPTS / "attest-plan.ps1", cwd, env)

    def test_absolute_pin_locks_the_pinned_plan(self) -> None:
        result = self.attest(self.parent, clean_env(PWF_PLAN_ROOT=str(self.project), PLAN_ID="plan-a"))
        combined = " ".join((result.stdout + result.stderr).split())
        self.assertNotIn("IsPathFullyQualified", combined)
        self.assertEqual(0, result.returncode, combined)
        self.assertTrue((self.project / ".planning" / "plan-a" / ".attestation").is_file(), combined)

    def test_relative_pin_is_refused(self) -> None:
        result = self.attest(self.parent, clean_env(PWF_PLAN_ROOT="project", PLAN_ID="plan-a"))
        combined = " ".join((result.stdout + result.stderr).split())
        self.assertNotEqual(0, result.returncode, combined)
        self.assertIn("absolute local path", combined)
        self.assertFalse((self.project / ".planning" / "plan-a" / ".attestation").exists())

    def test_unc_pin_is_refused(self) -> None:
        result = self.attest(self.parent, clean_env(PWF_PLAN_ROOT=r"\\localhost\C$\project", PLAN_ID="plan-a"))
        combined = " ".join((result.stdout + result.stderr).split())
        self.assertNotEqual(0, result.returncode, combined)
        self.assertIn("absolute local path", combined)


@unittest.skipUnless(WINDOWS_POWERSHELL, "requires Windows PowerShell 5.1")
class AttesterPinWindowsPowerShellTests(AttesterPinContract, unittest.TestCase):
    exe = WINDOWS_POWERSHELL


@unittest.skipUnless(PWSH and os.name == "nt", "requires pwsh on Windows (the attester is Windows-only)")
class AttesterPinPwshTests(AttesterPinContract, unittest.TestCase):
    exe = PWSH


if __name__ == "__main__":
    unittest.main()
