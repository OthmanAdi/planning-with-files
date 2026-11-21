"""plan-doctor.sh classifies injection output structurally, not by substring (#236).

The injection `case` block matched control strings against `$OUT`, which
carries the plan body VERBATIM inside the `===BEGIN-PWF-DATA===` fences. Two
defects followed:

  1. False WARN. A plan whose phase line read "fix the false PLAN TAMPERED
     warning in plan-doctor" reported a hash mismatch while being correctly
     attested. Not avoidable by correct usage: no documentation reserves those
     phrases.
  2. False PASS. The `PWF_PLAN_ROOT` arm matched
     "PWF_PLAN_ROOT is not a directory", which is not a substring of what
     inject-plan.sh emits. The arm was dead code, execution fell to the
     success arm, and a fully dark-hooks state reported PASS with the refusal
     notice's own byte count. The file's adjacent comment already warned that
     "reporting its byte count as PASS told a dark user their hooks were fine".

Classification now branches on the frame first: every refusal path exits before
frame_file runs, so a frame proves injection happened, and output without one
is by construction a notice. The default arm therefore WARNS, which is what
makes a future literal drift degrade to a noisy warning instead of a silent
PASS. Arm 2 below is the test that would have caught defect 1; arm 3 is the one
that would have caught defect 2; the stub test pins the drift property itself.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"

# Every control string the case block matches on, as ordinary plan prose.
CONTROL_LITERALS = """# Task Plan: doctor literals

## Phases
### Phase 1
- [ ] fix the false PLAN TAMPERED warning in plan-doctor
- [ ] audit the v3 mode requires attested plan branch
- [ ] document what Session isolation is armed means
- [ ] reword the Ambiguous plan notice
- [ ] check PWF_PLAN_ROOT is not a supported absolute local directory wording
- [ ] and PLAN_ID does not name a plan directory too
- [ ] [planning-with-files] Plan injection could not verify the plan path: it needs realpath, readlink -f, or an absolute PWF_TRUSTED_PYTHON or PYTHON_BIN path to Python 3.8 or newer, and none was usable, so nothing was injected.
"""


def have_sh() -> bool:
    return shutil.which("sh") is not None


def doctor_injection_line(stdout: str) -> str:
    for line in stdout.splitlines():
        if " injection:" in line:
            return line
    return ""


@unittest.skipUnless(have_sh(), "requires a POSIX sh")
class PlanDoctorClassificationTests(unittest.TestCase):
    def setUp(self) -> None:
        import tempfile

        self.tempdir = tempfile.TemporaryDirectory(prefix="pwf-doctor-")
        self.root = Path(self.tempdir.name)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _doctor(self, env_extra: dict | None = None, scripts: Path | None = None):
        env = os.environ.copy()
        for key in ("PLAN_ID", "PWF_PLAN_ROOT", "PLANNING_DISABLED"):
            env.pop(key, None)
        if env_extra:
            env.update(env_extra)
        return subprocess.run(
            ["sh", str((scripts or SCRIPTS) / "plan-doctor.sh")],
            cwd=str(self.root),
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
        )

    def _attest(self):
        env = os.environ.copy()
        for key in ("PLAN_ID", "PWF_PLAN_ROOT"):
            env.pop(key, None)
        return subprocess.run(
            ["sh", str(SCRIPTS / "attest-plan.sh")],
            cwd=str(self.root), env=env, capture_output=True, text=True, timeout=120,
        )

    def test_real_tamper_warns(self):
        (self.root / "task_plan.md").write_text("# plan\n- [ ] one\n", encoding="utf-8")
        self.assertEqual(0, self._attest().returncode)
        (self.root / "task_plan.md").write_text("# plan\n- [ ] two\n", encoding="utf-8")
        line = doctor_injection_line(self._doctor().stdout)
        self.assertTrue(line.startswith("WARN"), line)
        self.assertIn("hash mismatch", line)

    def test_plan_quoting_every_control_literal_still_passes(self):
        """Defect 1. The framing is the trust boundary; the doctor used to
        discard it by grepping the whole blob."""
        (self.root / "task_plan.md").write_text(CONTROL_LITERALS, encoding="utf-8")
        self.assertEqual(0, self._attest().returncode)
        line = doctor_injection_line(self._doctor().stdout)
        self.assertTrue(line.startswith("PASS"), line)

    def test_dark_hooks_never_report_pass(self):
        """Defect 2. A false PASS is worse than a false WARN: nobody
        investigates a PASS."""
        line = doctor_injection_line(
            self._doctor({"PWF_PLAN_ROOT": "/nonexistent/qhx4472"}).stdout
        )
        self.assertFalse(line.startswith("PASS"), line)
        self.assertIn("PWF_PLAN_ROOT", line)

    def test_rejected_plan_id_binding_never_reports_pass(self):
        (self.root / "task_plan.md").write_text("# plan\n", encoding="utf-8")
        line = doctor_injection_line(
            self._doctor({"PLAN_ID": "2026-07-21-nonexistent"}).stdout
        )
        self.assertFalse(line.startswith("PASS"), line)

    def test_no_plan_present_is_still_the_silent_ok(self):
        line = doctor_injection_line(self._doctor().stdout)
        self.assertTrue(line.startswith("PASS"), line)
        self.assertIn("no plan exists", line)

    def test_an_unrecognized_refusal_banner_warns_instead_of_passing(self):
        """The drift property itself, which is the actual bug behind defect 2.

        A stub inject-plan.sh emits a refusal wording no arm knows. Under the
        old default arm this reported PASS and counted the notice's bytes as
        plan context. It must now warn, so a future reworded or translated
        banner degrades noisily rather than silently.
        """
        stubs = self.root / "stub-scripts"
        stubs.mkdir()
        shutil.copy2(SCRIPTS / "plan-doctor.sh", stubs / "plan-doctor.sh")
        shutil.copy2(SCRIPTS / "resolve-plan-dir.sh", stubs / "resolve-plan-dir.sh")
        (stubs / "inject-plan.sh").write_text(
            "#!/bin/sh\n"
            "echo '[planning-with-files] a refusal wording nothing matches yet'\n",
            encoding="utf-8",
            newline="\n",
        )
        (self.root / "task_plan.md").write_text("# plan\n", encoding="utf-8")
        line = doctor_injection_line(self._doctor(scripts=stubs).stdout)
        self.assertTrue(line.startswith("WARN"), line)
        self.assertIn("BEGIN-PWF-DATA", line)

    @unittest.skipIf(os.name == "nt", "MSYS sh requires runtime DLL directories on PATH")
    def test_missing_canonicalizer_notice_reports_specific_failure(self):
        sh = shutil.which("sh")
        assert sh is not None
        bin_dir = self.root / "sh-only-bin"
        bin_dir.mkdir()
        (bin_dir / Path(sh).name).symlink_to(sh)
        (self.root / "task_plan.md").write_text("# plan\n", encoding="utf-8")
        result = subprocess.run(
            [sh, str(SCRIPTS / "plan-doctor.sh")],
            cwd=str(self.root),
            env={"PATH": str(bin_dir)},
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        line = doctor_injection_line(result.stdout)
        self.assertTrue(line.startswith("FAIL"), line)
        self.assertIn("could not verify the plan path", line)
        self.assertNotIn("does not recognize", line)


if __name__ == "__main__":
    unittest.main()
