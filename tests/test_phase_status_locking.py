"""Concurrency and fail-closed tests for the phase-status writer pair."""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = REPO_ROOT / "skills" / "planning-with-files" / "scripts"
PHASE_SH = SCRIPT_DIR / "phase-status.sh"
PHASE_PS1 = SCRIPT_DIR / "phase-status.ps1"
ROOT_PHASE_SH = REPO_ROOT / "scripts" / "phase-status.sh"
ROOT_PHASE_PS1 = REPO_ROOT / "scripts" / "phase-status.ps1"
SH = shutil.which("sh")
POWERSHELL = shutil.which("pwsh") or shutil.which("powershell")


class PhaseStatusLockFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="pwf-phase-lock-"))
        self.plan_dir = self.tmp / ".planning" / "p"
        self.plan_dir.mkdir(parents=True)
        (self.tmp / ".planning" / ".active_plan").write_text(
            "p\n", encoding="utf-8"
        )
        self.env = os.environ.copy()
        self.env["PLAN_ID"] = "p"
        self.write_plan(8)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    @property
    def plan_file(self) -> Path:
        return self.plan_dir / "task_plan.md"

    @property
    def lock_dir(self) -> Path:
        return self.plan_dir / ".pwf-locks" / "phase-status.lock"

    def write_plan(self, phases: int) -> None:
        body = ["# Task Plan"]
        for phase in range(1, phases + 1):
            body.extend(
                [f"### Phase {phase}: Work", "- **Status:** pending"]
            )
        self.plan_file.write_text("\n".join(body) + "\n", encoding="utf-8")

    def sh_command(self, phase: int, status: str = "complete") -> list[str]:
        assert SH is not None
        return [SH, str(PHASE_SH), str(phase), status]

    def ps_command(self, phase: int, status: str = "complete") -> list[str]:
        assert POWERSHELL is not None
        command = [POWERSHELL, "-NoProfile"]
        if os.name == "nt":
            command.extend(["-ExecutionPolicy", "Bypass"])
        command.extend(["-File", str(PHASE_PS1), str(phase), status])
        return command

    def run_command(self, command: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(
            command,
            cwd=self.tmp,
            env=self.env,
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
            timeout=12,
        )

    def false_success_mkdir_env(self, expected_callers: int = 2) -> dict[str, str]:
        """Return an env where mkdir reports success to concurrent creators.

        This models the Windows native uutils behavior from issue #281 without
        depending on that utility being installed on the test runner. The
        helper holds the first lock-directory calls until every writer has
        arrived, then lets all of them return zero for the same directory.
        """
        fake_bin = self.tmp / "false-success-bin"
        fake_bin.mkdir()
        fake_mkdir = fake_bin / "mkdir"
        fake_mkdir.write_text(
            """#!/bin/sh
if [ "${1:-}" = "-p" ]; then
    PATH=/usr/bin:/bin
    export PATH
    exec mkdir "$@"
fi
PATH=/usr/bin:/bin
export PATH
mkdir "$@" 2>/dev/null || true
barrier="$PWF_TEST_MKDIR_BARRIER"
mkdir -p "$barrier"
: > "$barrier/$$"
attempts=0
while [ "$(find "$barrier" -type f 2>/dev/null | wc -l | tr -d ' ')" -lt "$PWF_TEST_MKDIR_CALLERS" ]; do
    attempts=$((attempts + 1))
    [ "$attempts" -lt 500 ] || exit 70
    sleep 0.01
done
# Deliberately report success even when another process created the directory.
exit 0
""",
            encoding="utf-8",
        )
        fake_mkdir.chmod(0o755)

        fake_awk = fake_bin / "awk"
        fake_awk.write_text(
            """#!/bin/sh
PATH=/usr/bin:/bin
export PATH
barrier="$PWF_TEST_AWK_BARRIER"
mkdir -p "$barrier"
snapshot="$barrier/source.$$"
cp "$6" "$snapshot" || exit 71
: > "$barrier/marker.$$"
# The mkdir shim has already released both contenders at the same instant.
# With the broken lock they both snapshot during this window; with the fixed
# lock the second writer cannot reach this point until the first one releases.
sleep 1
exec awk "$1" "$2" "$3" "$4" "$5" "$snapshot"
""",
            encoding="utf-8",
        )
        fake_awk.chmod(0o755)

        env = self.env.copy()
        env["PWF_TEST_MKDIR_BARRIER"] = "./false-success-barrier"
        env["PWF_TEST_AWK_BARRIER"] = "./false-success-awk-barrier"
        env["PWF_TEST_MKDIR_CALLERS"] = str(expected_callers)
        return env

    def adversarial_sh_command(
        self, phase: int, status: str = "complete"
    ) -> list[str]:
        """Run phase-status with the fixture's mkdir/awk shims first on PATH."""
        assert SH is not None
        command = (
            'PATH="./false-success-bin:$PATH"; export PATH; '
            'exec sh "$1" "$2" "$3"'
        )
        return [
            SH,
            "-c",
            command,
            "phase-status-lock-test",
            str(PHASE_SH),
            str(phase),
            status,
        ]


class PhaseStatusLockStaticTests(unittest.TestCase):
    def test_root_and_canonical_writers_use_same_fail_closed_sentinel(self) -> None:
        for root_script, canonical_script in (
            (ROOT_PHASE_SH, PHASE_SH),
            (ROOT_PHASE_PS1, PHASE_PS1),
        ):
            with self.subTest(script=canonical_script.name):
                root_source = root_script.read_text(encoding="utf-8")
                canonical_source = canonical_script.read_text(encoding="utf-8")
                self.assertEqual(root_source, canonical_source)
                self.assertIn(".pwf-locks", canonical_source)
                self.assertIn("phase-status.lock", canonical_source)
                self.assertNotIn(".write_lock", canonical_source)
                self.assertNotIn("flock", canonical_source)

    def test_phase_read_occurs_after_lock_acquisition(self) -> None:
        shell_source = PHASE_SH.read_text(encoding="utf-8")
        self.assertLess(
            shell_source.index("acquire_lock\n"),
            shell_source.index("if ! grep -q"),
        )

        ps_source = PHASE_PS1.read_text(encoding="utf-8")
        self.assertLess(
            ps_source.index("$lock = Enter-PwfDirectoryLock"),
            ps_source.index("$lines = Get-Content"),
        )

    def test_lock_ownership_is_claimed_with_exclusive_file_creation(self) -> None:
        shell_source = PHASE_SH.read_text(encoding="utf-8")
        self.assertIn("set -C", shell_source)

        ps_source = PHASE_PS1.read_text(encoding="utf-8")
        self.assertIn("[System.IO.FileMode]::CreateNew", ps_source)


@unittest.skipUnless(SH, "sh not available")
class ShellPhaseStatusLockTests(PhaseStatusLockFixture):
    def test_held_lock_times_out_without_plan_mutation_or_owner_removal(self) -> None:
        self.lock_dir.mkdir(parents=True)
        owner = self.lock_dir / ".owner"
        owner.write_text("external-owner\n", encoding="utf-8")
        before = self.plan_file.read_bytes()

        started = time.monotonic()
        result = self.run_command(self.sh_command(1))
        elapsed = time.monotonic() - started

        self.assertNotEqual(0, result.returncode)
        self.assertGreaterEqual(elapsed, 4.0)
        self.assertIn("Timed out waiting for lock", result.stderr)
        self.assertEqual(before, self.plan_file.read_bytes())
        self.assertEqual("external-owner", owner.read_text(encoding="utf-8").strip())
        self.assertTrue(self.lock_dir.is_dir())
        self.assertEqual([], list(self.plan_dir.glob("task_plan.md.tmp.*")))

    def test_concurrent_distinct_phase_updates_are_not_lost(self) -> None:
        processes = [
            subprocess.Popen(
                self.sh_command(phase),
                cwd=self.tmp,
                env=self.env,
                text=True,
                encoding="utf-8",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            for phase in range(1, 3)
        ]
        results = [process.communicate(timeout=15) for process in processes]

        failures = [
            (process.returncode, stdout, stderr)
            for process, (stdout, stderr) in zip(processes, results)
            if process.returncode != 0
        ]
        self.assertEqual([], failures)
        plan = self.plan_file.read_text(encoding="utf-8")
        self.assertEqual(2, plan.count("- **Status:** complete"))
        self.assertEqual(6, plan.count("- **Status:** pending"))
        self.assertFalse(self.lock_dir.exists())

    def test_false_successful_mkdir_cannot_admit_two_writers(self) -> None:
        # The awk shim snapshots before its barrier. If both writers enter the
        # critical section, both therefore rewrite the same pre-update bytes.
        self.write_plan(2)

        env = self.false_success_mkdir_env()
        processes = [
            subprocess.Popen(
                self.adversarial_sh_command(phase),
                cwd=self.tmp,
                env=env,
                text=True,
                encoding="utf-8",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            for phase in range(1, 3)
        ]
        results = [process.communicate(timeout=20) for process in processes]

        failures = [
            (process.returncode, stdout, stderr)
            for process, (stdout, stderr) in zip(processes, results)
            if process.returncode != 0
        ]
        self.assertEqual([], failures)
        self.assertGreaterEqual(
            len(list((self.tmp / "false-success-barrier").iterdir())),
            2,
            "the adversarial mkdir shim was not exercised",
        )
        self.assertGreaterEqual(
            len(
                list(
                    (self.tmp / "false-success-awk-barrier").glob("marker.*")
                )
            ),
            2,
            "the synchronized awk shim was not exercised",
        )
        plan = self.plan_file.read_text(encoding="utf-8")
        self.assertEqual(2, plan.count("- **Status:** complete"))
        self.assertFalse(self.lock_dir.exists())


@unittest.skipUnless(POWERSHELL and os.name == "nt", "Windows PowerShell unavailable")
class PowerShellPhaseStatusLockTests(PhaseStatusLockFixture):
    def test_held_shell_compatible_lock_fails_closed(self) -> None:
        self.lock_dir.mkdir(parents=True)
        owner = self.lock_dir / ".owner"
        owner.write_text("shell-owner\n", encoding="utf-8")
        before = self.plan_file.read_bytes()

        result = self.run_command(self.ps_command(1))

        self.assertNotEqual(0, result.returncode)
        self.assertIn("Timed out waiting for lock", result.stderr)
        self.assertEqual(before, self.plan_file.read_bytes())
        self.assertEqual("shell-owner", owner.read_text(encoding="utf-8").strip())
        self.assertTrue(self.lock_dir.is_dir())
        self.assertEqual([], list(self.plan_dir.glob("task_plan.md.tmp.*")))

    @unittest.skipUnless(SH, "sh not available")
    def test_shell_and_powershell_serialize_on_the_same_directory(self) -> None:
        commands = [
            self.sh_command(phase) if phase % 2 else self.ps_command(phase)
            for phase in range(1, 3)
        ]
        processes = [
            subprocess.Popen(
                command,
                cwd=self.tmp,
                env=self.env,
                text=True,
                encoding="utf-8",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            for command in commands
        ]
        results = [process.communicate(timeout=20) for process in processes]

        failures = [
            (process.returncode, stdout, stderr)
            for process, (stdout, stderr) in zip(processes, results)
            if process.returncode != 0
        ]
        self.assertEqual([], failures)
        plan = self.plan_file.read_text(encoding="utf-8")
        self.assertEqual(2, plan.count("- **Status:** complete"))
        self.assertEqual(6, plan.count("- **Status:** pending"))
        self.assertFalse(self.lock_dir.exists())


if __name__ == "__main__":
    unittest.main()
