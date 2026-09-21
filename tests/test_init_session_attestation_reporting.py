"""Regression coverage for init-session attestation status reporting (#276)."""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INIT_SH = REPO_ROOT / "scripts" / "init-session.sh"
INIT_PS1 = REPO_ROOT / "scripts" / "init-session.ps1"
SH = shutil.which("sh")
POWERSHELL = shutil.which("powershell") or shutil.which("powershell.exe")


def flat(text: str) -> str:
    return " ".join(text.split())


def child_env() -> dict[str, str]:
    return {
        key: value
        for key, value in os.environ.items()
        if key not in {"PLAN_ID", "PWF_PLAN_ROOT"}
    }


def make_bundle(
    root: Path,
    initializer: Path,
    attester_name: str,
    attester_content: str,
) -> Path:
    skill = root / "skill"
    scripts = skill / "scripts"
    scripts.mkdir(parents=True)
    shutil.copytree(REPO_ROOT / "templates", skill / "templates")
    copied_initializer = scripts / initializer.name
    shutil.copy2(initializer, copied_initializer)
    (scripts / attester_name).write_text(attester_content, encoding="utf-8")
    return copied_initializer


@unittest.skipUnless(SH, "requires sh")
class InitSessionShellAttestationReportingTests(unittest.TestCase):
    def test_success_still_reports_attested(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = subprocess.run(
                [SH, str(INIT_SH), "--autonomous"],
                cwd=str(root),
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=False,
                env=child_env(),
            )

            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertTrue((root / ".plan-attestation").is_file())
            self.assertIn(
                "Mode: autonomous (attested, gate counter reset)",
                result.stdout,
            )

    def test_nonzero_attester_is_reported_without_aborting_init(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            initializer = make_bundle(
                root,
                INIT_SH,
                "attest-plan.sh",
                "#!/bin/sh\n"
                "printf '%s\\n' '[plan-attest] synthetic shell failure' >&2\n"
                "exit 17\n",
            )
            project = root / "project"
            project.mkdir()

            result = subprocess.run(
                [SH, str(initializer), "--autonomous"],
                cwd=str(project),
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=False,
                env=child_env(),
            )

            output = flat(result.stdout + result.stderr)
            self.assertEqual(0, result.returncode, output)
            self.assertIn("NOT attested: [plan-attest] synthetic shell failure", output)
            self.assertIn("run attest-plan.sh before the first hook fire", output)
            self.assertNotIn("Mode: autonomous (attested, gate counter reset)", output)
            self.assertEqual("0", (project / ".stop_blocks").read_text(encoding="ascii").strip())
            self.assertFalse((project / ".plan-attestation").exists())


@unittest.skipUnless(POWERSHELL, "requires Windows PowerShell")
class InitSessionPowerShellAttestationReportingTests(unittest.TestCase):
    def run_initializer(self, initializer: Path, project: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                POWERSHELL,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(initializer),
                "-Autonomous",
            ],
            cwd=str(project),
            text=True,
            encoding="utf-8-sig",
            capture_output=True,
            check=False,
            env=child_env(),
        )

    def assert_failure_reported(
        self,
        result: subprocess.CompletedProcess[str],
        project: Path,
        reason: str,
        attester_name: str,
    ) -> None:
        output = flat(result.stdout + result.stderr)
        self.assertEqual(0, result.returncode, output)
        self.assertIn(f"NOT attested: {reason}", output)
        self.assertIn(f"run {attester_name} before the first hook fire", output)
        self.assertNotIn("Mode: autonomous (attested, gate counter reset)", output)
        self.assertEqual("0", (project / ".stop_blocks").read_text(encoding="ascii").strip())
        self.assertFalse((project / ".plan-attestation").exists())

    def test_success_still_reports_attested(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            result = self.run_initializer(INIT_PS1, project)

            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertTrue((project / ".plan-attestation").is_file())
            self.assertIn(
                "Mode: autonomous (attested, gate counter reset)",
                result.stdout,
            )

    def test_nonzero_attester_is_reported_without_aborting_init(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            if os.name == "nt":
                attester_name = "attest-plan.ps1"
                attester_content = (
                    'Write-Output "[plan-attest] synthetic status failure"\n'
                    "exit 17\n"
                )
            else:
                attester_name = "attest-plan.sh"
                attester_content = (
                    "#!/bin/sh\n"
                    "printf '%s\\n' '[plan-attest] synthetic status failure' >&2\n"
                    "exit 17\n"
                )
            initializer = make_bundle(
                root,
                INIT_PS1,
                attester_name,
                attester_content,
            )
            project = root / "project"
            project.mkdir()

            result = self.run_initializer(initializer, project)

            self.assert_failure_reported(
                result,
                project,
                "[plan-attest] synthetic status failure",
                attester_name,
            )

    @unittest.skipUnless(os.name == "nt", "PowerShell attester exceptions are Windows-only")
    def test_attester_exception_is_reported_without_aborting_init(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            initializer = make_bundle(
                root,
                INIT_PS1,
                "attest-plan.ps1",
                'throw "[plan-attest] synthetic exception"\n',
            )
            project = root / "project"
            project.mkdir()

            result = self.run_initializer(initializer, project)

            self.assert_failure_reported(
                result,
                project,
                "[plan-attest] synthetic exception",
                "attest-plan.ps1",
            )


if __name__ == "__main__":
    unittest.main()
