"""Regression tests for the plan-attestation flow (v2.37.0).

Verifies the attest-plan.sh helper:
  - Computes a SHA-256 of task_plan.md and stores it.
  - --show prints the stored hash.
  - --clear removes the attestation file.
  - Detects tampering (file change after attest -> stored hash != fresh hash).
  - Resolves parallel plans (.planning/<slug>/task_plan.md) ahead of legacy.

Skipped on platforms without sh in PATH (the helper is POSIX shell).
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from unittest import mock
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "attest-plan.sh"
RESOLVER = REPO_ROOT / "scripts" / "resolve-plan-dir.sh"


def have_sh() -> bool:
    return shutil.which("sh") is not None


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@unittest.skipUnless(have_sh(), "sh not available on this platform")
class PlanAttestationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="pwf-attest-"))
        # Copy resolver next to attest-plan so the helper can find it.
        self.scripts_dir = self.tmp / "scripts"
        self.scripts_dir.mkdir()
        shutil.copy2(SCRIPT, self.scripts_dir / "attest-plan.sh")
        shutil.copy2(RESOLVER, self.scripts_dir / "resolve-plan-dir.sh")
        os.chmod(self.scripts_dir / "attest-plan.sh", 0o755)
        os.chmod(self.scripts_dir / "resolve-plan-dir.sh", 0o755)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(
        self,
        *args: str,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess:
        run_env = os.environ.copy()
        runtime_home = self.tmp / "home"
        runtime_home.mkdir(exist_ok=True)
        run_env["HOME"] = str(runtime_home)
        run_env.pop("PLAN_ID", None)
        run_env.pop("PWF_PLAN_ROOT", None)
        if env:
            run_env.update(env)
        return subprocess.run(
            ["sh", str(self.scripts_dir / "attest-plan.sh"), *args],
            cwd=str(cwd or self.tmp),
            env=run_env,
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
        )

    def test_legacy_attest_writes_root_attestation(self) -> None:
        plan = self.tmp / "task_plan.md"
        plan.write_text("# Plan v1\nphase 1\n", encoding="utf-8")

        result = self._run()
        self.assertEqual(0, result.returncode, result.stderr)

        attest = self.tmp / ".plan-attestation"
        self.assertTrue(attest.exists(), "expected .plan-attestation at project root")
        self.assertEqual(sha256_of(plan), attest.read_text().strip())

    def test_show_prints_stored_hash(self) -> None:
        plan = self.tmp / "task_plan.md"
        plan.write_text("content", encoding="utf-8")
        self._run()

        result = self._run("--show")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn(sha256_of(plan), result.stdout)

    def test_clear_removes_attestation(self) -> None:
        plan = self.tmp / "task_plan.md"
        plan.write_text("content", encoding="utf-8")
        self._run()
        self.assertTrue((self.tmp / ".plan-attestation").exists())

        result = self._run("--clear")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertFalse((self.tmp / ".plan-attestation").exists())

    def test_tamper_changes_hash(self) -> None:
        plan = self.tmp / "task_plan.md"
        plan.write_text("approved content\n", encoding="utf-8")
        self._run()
        attested = (self.tmp / ".plan-attestation").read_text().strip()

        plan.write_text("approved content\nsneaky injection\n", encoding="utf-8")
        fresh = sha256_of(plan)

        self.assertNotEqual(
            attested,
            fresh,
            "hash must differ after tampering for the hook gate to fire",
        )

    def test_parallel_plan_attest_writes_into_plan_dir(self) -> None:
        plan_dir = self.tmp / ".planning" / "2026-05-05-feature-x"
        plan_dir.mkdir(parents=True)
        (plan_dir / "task_plan.md").write_text("phase A\n", encoding="utf-8")
        (self.tmp / ".planning" / ".active_plan").write_text(
            "2026-05-05-feature-x", encoding="utf-8"
        )

        result = self._run()
        self.assertEqual(0, result.returncode, result.stderr)

        attest = plan_dir / ".attestation"
        self.assertTrue(attest.exists(), "expected attestation inside the plan dir")
        self.assertFalse(
            (self.tmp / ".plan-attestation").exists(),
            "must not write the legacy file when an active plan dir exists",
        )

    def test_attest_from_inside_plan_dir_updates_slug_attestation(self) -> None:
        plan_dir = self.tmp / ".planning" / "2026-05-05-feature-x"
        plan_dir.mkdir(parents=True)
        plan = plan_dir / "task_plan.md"
        plan.write_text("phase A\n", encoding="utf-8")
        (self.tmp / ".planning" / ".active_plan").write_text(
            "2026-05-05-feature-x", encoding="utf-8"
        )

        initial = self._run()
        self.assertEqual(0, initial.returncode, initial.stderr)
        attest = plan_dir / ".attestation"
        initial_hash = attest.read_text(encoding="utf-8").strip()

        plan.write_text("phase A\nphase B\n", encoding="utf-8")
        nested = self._run(cwd=plan_dir)

        self.assertEqual(0, nested.returncode, nested.stderr)
        self.assertNotEqual(initial_hash, sha256_of(plan))
        self.assertEqual(sha256_of(plan), attest.read_text(encoding="utf-8").strip())
        self.assertFalse(
            (plan_dir / ".plan-attestation").exists(),
            "nested slug invocation must not create a legacy attestation",
        )

    def test_failed_explicit_selector_does_not_fallback_inside_slug(self) -> None:
        plan_dir = self.tmp / ".planning" / "2026-05-05-feature-x"
        plan_dir.mkdir(parents=True)
        (plan_dir / "task_plan.md").write_text("phase A\n", encoding="utf-8")

        selectors = {
            "PLAN_ID": "missing-plan",
            "PWF_PLAN_ROOT": str(self.tmp / "missing-project"),
        }
        for name, value in selectors.items():
            with self.subTest(selector=name):
                (plan_dir / ".attestation").unlink(missing_ok=True)
                (plan_dir / ".plan-attestation").unlink(missing_ok=True)

                result = self._run(cwd=plan_dir, env={name: value})

                self.assertNotEqual(0, result.returncode)
                self.assertFalse((plan_dir / ".attestation").exists())
                self.assertFalse((plan_dir / ".plan-attestation").exists())

    def test_target_root_attests_root_while_named_plan_is_active(self) -> None:
        root_plan = self.tmp / "task_plan.md"
        root_plan.write_text("root roadmap\n", encoding="utf-8")
        plan_dir = self.tmp / ".planning" / "2026-09-26-live-ticket"
        plan_dir.mkdir(parents=True)
        (plan_dir / "task_plan.md").write_text("live ticket\n", encoding="utf-8")
        (self.tmp / ".planning" / ".active_plan").write_text(
            "2026-09-26-live-ticket\n", encoding="utf-8"
        )

        result = self._run("--target", "root")

        self.assertEqual(0, result.returncode, result.stderr)
        root_attest = self.tmp / ".plan-attestation"
        self.assertEqual(sha256_of(root_plan), root_attest.read_text().strip())
        self.assertFalse((plan_dir / ".attestation").exists())
        self.assertIn("Plan: ./task_plan.md", result.stdout)
        self.assertIn("Attestation: ./.plan-attestation", result.stdout)

    def test_target_named_plan_attests_exact_plan(self) -> None:
        selected = self.tmp / ".planning" / "2026-09-26-selected"
        active = self.tmp / ".planning" / "2026-09-26-active"
        selected.mkdir(parents=True)
        active.mkdir(parents=True)
        selected_plan = selected / "task_plan.md"
        selected_plan.write_text("selected\n", encoding="utf-8")
        (active / "task_plan.md").write_text("active\n", encoding="utf-8")
        (self.tmp / ".planning" / ".active_plan").write_text(
            "2026-09-26-active\n", encoding="utf-8"
        )

        result = self._run("--target", "2026-09-26-selected")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(
            sha256_of(selected_plan),
            (selected / ".attestation").read_text().strip(),
        )
        self.assertFalse((active / ".attestation").exists())

    def test_unresolvable_target_fails_without_fallback_or_write(self) -> None:
        root_plan = self.tmp / "task_plan.md"
        root_plan.write_text("root decoy\n", encoding="utf-8")
        active = self.tmp / ".planning" / "2026-09-26-active"
        active.mkdir(parents=True)
        (active / "task_plan.md").write_text("active decoy\n", encoding="utf-8")
        (self.tmp / ".planning" / ".active_plan").write_text(
            "2026-09-26-active\n", encoding="utf-8"
        )

        result = self._run("--target", "2026-09-26-missing")

        self.assertNotEqual(0, result.returncode)
        self.assertIn("--target 2026-09-26-missing", result.stderr)
        self.assertFalse((self.tmp / ".plan-attestation").exists())
        self.assertFalse((active / ".attestation").exists())

    def test_default_target_resolution_is_unchanged(self) -> None:
        root_plan = self.tmp / "task_plan.md"
        root_plan.write_text("root roadmap\n", encoding="utf-8")
        active = self.tmp / ".planning" / "2026-09-26-active"
        active.mkdir(parents=True)
        active_plan = active / "task_plan.md"
        active_plan.write_text("active ticket\n", encoding="utf-8")
        (self.tmp / ".planning" / ".active_plan").write_text(
            "2026-09-26-active\n", encoding="utf-8"
        )

        result = self._run()

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(
            sha256_of(active_plan),
            (active / ".attestation").read_text().strip(),
        )
        self.assertFalse((self.tmp / ".plan-attestation").exists())

    def test_empty_target_refuses_without_attesting_active_plan(self) -> None:
        active = self.tmp / ".planning" / "active"
        active.mkdir(parents=True)
        (active / "task_plan.md").write_text("active", encoding="utf-8")
        (self.tmp / "task_plan.md").write_text("root", encoding="utf-8")
        result = self._run("--target", "")
        self.assertNotEqual(0, result.returncode)
        self.assertFalse((active / ".attestation").exists())
        self.assertFalse((self.tmp / ".plan-attestation").exists())

    def test_extra_arguments_refuse_without_clearing_another_plan(self) -> None:
        active = self.tmp / ".planning" / "active"
        active.mkdir(parents=True)
        (active / "task_plan.md").write_text("active", encoding="utf-8")
        (self.tmp / "task_plan.md").write_text("root", encoding="utf-8")
        root_attest = self.tmp / ".plan-attestation"
        active_attest = active / ".attestation"
        for args in (("--show", "--target", "root"),
                     ("--clear", "--target", "root"),
                     ("--target", "root", "--clear"), ("", "extra")):
            with self.subTest(args=args):
                root_attest.write_text("root sentinel", encoding="utf-8")
                active_attest.write_text("active sentinel", encoding="utf-8")
                result = self._run(*args)
                self.assertNotEqual(0, result.returncode)
                self.assertEqual("root sentinel", root_attest.read_text())
                self.assertEqual("active sentinel", active_attest.read_text())

    def test_targets_honor_project_pin_and_preserve_active_pointer(self) -> None:
        pinned = self.tmp / "pinned"
        for project in (self.tmp, pinned):
            active = project / ".planning" / "active"
            active.mkdir(parents=True)
            (active / "task_plan.md").write_text(str(project), encoding="utf-8")
            (project / "task_plan.md").write_text("root " + str(project), encoding="utf-8")
            (project / ".planning" / ".active_plan").write_bytes(b"active\r\n")
        for target, plan, attestation in (
            ("root", pinned / "task_plan.md", pinned / ".plan-attestation"),
            ("active", pinned / ".planning/active/task_plan.md", pinned / ".planning/active/.attestation"),
        ):
            with self.subTest(target=target):
                result = self._run("--target", target, env={
                    "PWF_PLAN_ROOT": pinned.as_posix(), "PLAN_ID": "missing"})
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertTrue(attestation.exists(), result.stdout)
                self.assertEqual(sha256_of(plan), attestation.read_text().strip())
                self.assertFalse((self.tmp / ".plan-attestation").exists())
                self.assertFalse((self.tmp / ".planning/active/.attestation").exists())
                self.assertEqual(b"active\r\n", (pinned / ".planning/.active_plan").read_bytes())
                self.assertEqual(b"active\r\n", (self.tmp / ".planning/.active_plan").read_bytes())

    def test_targets_reject_invalid_project_pin_without_cwd_fallback(self) -> None:
        active = self.tmp / ".planning" / "active"
        active.mkdir(parents=True)
        (active / "task_plan.md").write_text("active", encoding="utf-8")
        (self.tmp / "task_plan.md").write_text("root", encoding="utf-8")
        for pin in ((self.tmp / "missing").as_posix(), "."):
            for target in ("root", "active"):
                with self.subTest(pin=pin, target=target):
                    result = self._run("--target", target, env={"PWF_PLAN_ROOT": pin})
                    self.assertNotEqual(0, result.returncode)
                    self.assertFalse((self.tmp / ".plan-attestation").exists())
                    self.assertFalse((active / ".attestation").exists())

    @unittest.skipUnless(os.name == "nt", "Windows native path spelling")
    def test_named_target_hashes_native_windows_project_pin(self) -> None:
        pinned = self.tmp / "pinned"
        active = pinned / ".planning" / "active"
        active.mkdir(parents=True)
        plan = active / "task_plan.md"
        plan.write_text("pinned plan", encoding="utf-8")
        result = self._run("--target", "active", env={"PWF_PLAN_ROOT": str(pinned)})
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(sha256_of(plan), (active / ".attestation").read_text().strip())

    def _make_directory_link(self, link: Path, target: Path) -> None:
        if os.name == "nt":
            made = subprocess.run(
                ["cmd", "/d", "/c", "mklink", "/J", str(link), str(target)],
                capture_output=True, text=True, check=False,
            )
            if made.returncode:
                self.skipTest("junction creation unavailable: " + made.stderr.strip())
        else:
            try:
                link.symlink_to(target, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")

    def test_target_rejects_linked_plan_directory(self) -> None:
        project = self.tmp / "project"
        (project / ".planning").mkdir(parents=True)
        outside = self.tmp / "outside"
        outside.mkdir()
        (outside / "task_plan.md").write_text("outside", encoding="utf-8")
        self._make_directory_link(project / ".planning/linked", outside)
        result = self._run("--target", "linked", cwd=project)
        self.assertNotEqual(0, result.returncode)
        self.assertFalse((outside / ".attestation").exists())

    def test_target_rejects_planning_directory_escape(self) -> None:
        project = self.tmp / "project"
        project.mkdir()
        outside = self.tmp / "outside"
        active = outside / "active"
        active.mkdir(parents=True)
        (active / "task_plan.md").write_text("outside", encoding="utf-8")
        self._make_directory_link(project / ".planning", outside)
        result = self._run("--target", "active", cwd=project)
        self.assertNotEqual(0, result.returncode)
        self.assertFalse((active / ".attestation").exists())

    def test_root_target_accepts_valid_linked_project_pin(self) -> None:
        project = self.tmp / "project"
        project.mkdir()
        plan = project / "task_plan.md"
        plan.write_text("pinned root", encoding="utf-8")
        (self.tmp / "task_plan.md").write_text("cwd decoy", encoding="utf-8")
        link = self.tmp / "project-link"
        self._make_directory_link(link, project)
        result = self._run("--target", "root", env={"PWF_PLAN_ROOT": link.as_posix()})
        self.assertEqual(0, result.returncode, result.stderr)
        attestation = project / ".plan-attestation"
        self.assertTrue(attestation.exists(), result.stdout)
        self.assertEqual(sha256_of(plan), attestation.read_text().strip())
        self.assertFalse((self.tmp / ".plan-attestation").exists())

    def test_targets_reject_linked_plan_files(self) -> None:
        outside = self.tmp / "outside.md"
        outside.write_text("outside", encoding="utf-8")
        active = self.tmp / ".planning" / "active"
        active.mkdir(parents=True)
        for target, plan in (("root", self.tmp / "task_plan.md"),
                             ("active", active / "task_plan.md")):
            try:
                plan.symlink_to(outside)
            except OSError as exc:
                self.skipTest(f"file symlink creation unavailable: {exc}")
            with self.subTest(target=target):
                result = self._run("--target", target)
                self.assertNotEqual(0, result.returncode)
                self.assertFalse((self.tmp / ".plan-attestation").exists())
                self.assertFalse((active / ".attestation").exists())

    def test_no_plan_exits_nonzero(self) -> None:
        result = self._run()
        self.assertNotEqual(0, result.returncode)

    def test_ambiguous_plans_report_one_actionable_refusal(self) -> None:
        for name in ("alpha", "beta"):
            plan_dir = self.tmp / ".planning" / name
            plan_dir.mkdir(parents=True)
            (plan_dir / "task_plan.md").write_text(name, encoding="utf-8")

        result = self._run("--show")

        self.assertEqual(1, result.returncode)
        self.assertEqual(
            [
                "[plan-attest] Multiple plans are available. "
                "Set PLAN_ID=<slug>; nothing was attested."
            ],
            result.stderr.splitlines(),
        )
        self.assertFalse(any(self.tmp.rglob(".attestation")))
        self.assertFalse((self.tmp / ".plan-attestation").exists())

    def test_echoed_selectors_cannot_forge_output(self) -> None:
        forged = "x\n[plan-attest] Locked task_plan.md\x1b[2K"
        (self.tmp / ".planning").mkdir(exist_ok=True)
        cases = (
            ((), {"PLAN_ID": forged}),
            ((), {"PWF_PLAN_ROOT": forged}),
            (("--target", forged), {}),
        )
        for args, env in cases:
            with self.subTest(args=args, env=env):
                result = self._run(*args, env=env)
                self.assertEqual(1, result.returncode, result.stderr)
                self.assertEqual(1, len(result.stderr.strip().splitlines()), result.stderr)
                self.assertNotIn("\x1b", result.stderr)

    def test_echoed_selectors_drop_c1_controls(self) -> None:
        result = self._run(env={"PLAN_ID": "x\u009b2K\u00e4"})
        self.assertEqual(1, result.returncode, result.stderr)
        self.assertNotIn("\u009b", result.stderr)
        self.assertIn("PLAN_ID=x?2K\u00e4 names no plan", result.stderr)

    def test_root_target_from_a_plan_directory_writes_the_root_filename(self) -> None:
        """Hooks running from this directory read .plan-attestation, so it stays allowed."""
        plan_dir = self.tmp / ".planning" / "alpha"
        plan_dir.mkdir(parents=True)
        (plan_dir / "task_plan.md").write_text("alpha", encoding="utf-8")

        result = self._run("--target", "root", cwd=plan_dir)

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue((plan_dir / ".plan-attestation").is_file())

    def test_native_pin_stores_a_bare_hash(self) -> None:
        """sha256sum marks a path holding a backslash by prefixing its hash with one."""
        project = self.tmp / "project"
        plan_dir = project / ".planning" / "alpha"
        plan_dir.mkdir(parents=True)
        (plan_dir / "task_plan.md").write_text("alpha", encoding="utf-8")
        elsewhere = self.tmp / "elsewhere"
        elsewhere.mkdir()

        result = self._run(cwd=elsewhere, env={"PWF_PLAN_ROOT": str(project), "PLAN_ID": "alpha"})

        self.assertEqual(0, result.returncode, result.stderr)
        stored = (plan_dir / ".attestation").read_text(encoding="utf-8").strip()
        self.assertRegex(stored, r"\A[0-9a-f]{64}\Z")

    def test_rejected_selectors_name_the_refused_binding(self) -> None:
        active = self.tmp / ".planning" / "active"
        active.mkdir(parents=True)
        (active / "task_plan.md").write_text("active decoy", encoding="utf-8")
        (self.tmp / "task_plan.md").write_text("root decoy", encoding="utf-8")
        missing_root = self.tmp / "missing-project"
        accepted_root = self.tmp / "accepted-project"
        accepted_root.mkdir()
        cases = (
            (("--target", "missing"), {}, "--target missing"),
            ((), {"PLAN_ID": "missing"}, "PLAN_ID=missing"),
            ((), {"PWF_PLAN_ROOT": str(missing_root)}, f"PWF_PLAN_ROOT={missing_root}"),
            (
                (),
                {"PLAN_ID": "missing", "PWF_PLAN_ROOT": str(missing_root)},
                f"PWF_PLAN_ROOT={missing_root}",
            ),
            (
                (),
                {"PLAN_ID": "missing", "PWF_PLAN_ROOT": str(accepted_root)},
                "PLAN_ID=missing",
            ),
            (
                (),
                {"PLAN_ID": "missing", "PWF_PLAN_ROOT": accepted_root.name},
                f"PWF_PLAN_ROOT={accepted_root.name}",
            ),
        )

        for args, env, refusal in cases:
            with self.subTest(refusal=refusal):
                result = self._run(*args, env=env)
                self.assertEqual(1, result.returncode)
                self.assertEqual(1, result.stderr.count(refusal), result.stderr)
                self.assertNotIn("No task_plan.md found", result.stderr)
                self.assertFalse((active / ".attestation").exists())
                self.assertFalse((self.tmp / ".plan-attestation").exists())

    def test_concurrent_attest_writes_do_not_corrupt_file(self) -> None:
        # v2.40 regression: parallel legacy-mode attestations used to race
        # via a non-atomic `> file` redirect, occasionally yielding a
        # truncated `.plan-attestation` (zero-length or partial hex) that the
        # hook then read as the expected hash, producing a false TAMPERED on
        # the next prompt. The fix is atomic temp+rename with an optional
        # flock guard. This test spawns 8 concurrent attestations on the same
        # plan file and asserts the resulting file is a complete 64-char hex
        # SHA-256 every time.
        import threading

        plan = self.tmp / "task_plan.md"
        plan.write_text("concurrent attestation target\n", encoding="utf-8")
        expected = sha256_of(plan)

        errors: list[str] = []
        results: list[int] = []
        lock = threading.Lock()

        def worker() -> None:
            res = self._run()
            with lock:
                results.append(res.returncode)
                if res.returncode != 0:
                    errors.append(res.stderr)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        self.assertFalse(errors, f"concurrent attest failures: {errors}")
        self.assertEqual(8, len(results))

        attest_file = self.tmp / ".plan-attestation"
        self.assertTrue(attest_file.exists())
        stored = attest_file.read_text().strip()
        self.assertEqual(
            64,
            len(stored),
            f"expected 64-char hex SHA, got {len(stored)} chars: {stored!r}",
        )
        self.assertEqual(
            expected,
            stored,
            "stored hash must match the (unchanged) plan content even under "
            "concurrent writes",
        )




    @unittest.skipUnless(os.name == "posix", "checkbox mode uses POSIX descriptors")
    def test_missing_atomic_link_support_uses_exclusive_directory(self):
        plan = self.tmp / "task_plan.md"
        plan.write_bytes(b"- [ ] ordinary task\n")
        commands = self.tmp / "bin"
        commands.mkdir()
        unsupported = commands / "ln"
        unsupported.write_text("#!/bin/sh\nexit 1\n", encoding="ascii")
        unsupported.chmod(0o755)
        result = self._run(env={"PATH": str(commands) + os.pathsep + os.environ["PATH"]})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.tmp / ".plan-attestation").read_text().strip(), sha256_of(plan))
        self.assertFalse((self.tmp / ".plan-attestation.writer-lock").exists())
        self.assertEqual(list(self.tmp.glob(".pwf-writer.*")), [])

    @unittest.skipUnless(os.name == "posix", "checkbox mode uses POSIX descriptors")
    def test_checkbox_only_enrollment_and_exact_bytes(self):
        plan = self.tmp / "task_plan.md"
        before = b"# Plan\r\n- [ ] one [ ]\r\n* [ ] two\r\n"
        after = before.replace(b"- [ ]", b"- [x]")
        plan.write_bytes(before)
        self.assertEqual(self._run().returncode, 0)
        self.assertFalse((self.tmp / ".attested-plan").exists())
        self.assertNotEqual(self._run("--checkbox-only").returncode, 0)
        result = self._run("--enable-checkbox-only", "--target", "root")
        self.assertEqual(result.returncode, 0, result.stderr)
        for other in (after.rstrip(), after.replace(b"one [ ]", b"one [x]"),
                      after + b"- [x] extra\n", after.replace(b"\r", b""),
                      after.replace(b"one", b"two")):
            with self.subTest(other=other):
                plan.write_bytes(other)
                self.assertNotEqual(self._run("--checkbox-only").returncode, 0)
                self.assertEqual((self.tmp / ".plan-attestation").read_text().strip(),
                                 hashlib.sha256(before).hexdigest())
        plan.write_bytes(after)
        result = self._run("--checkbox-only")
        self.assertEqual(result.returncode, 0, result.stderr)
        plan.write_bytes(before)
        self.assertNotEqual(self._run("--checkbox-only").returncode, 0)
        plan.write_bytes(after.replace(b"* [ ]", b"* [x]"))
        self.assertEqual(self._run("--checkbox-only").returncode, 0)
        self.assertEqual(self._run("--clear").returncode, 0)
        self.assertEqual(list((self.tmp / "home" / ".pwf-checkbox-v1").iterdir()), [])

    @unittest.skipUnless(os.name == "posix", "checkbox mode uses POSIX descriptors")
    def test_checkbox_only_preserves_unrelated_metadata(self):
        (self.tmp / "task_plan.md").write_bytes(b"- [ ] one\n")
        other = self.tmp / "unrelated"
        other.write_bytes(b"keep")
        metadata = self.tmp / "home" / ".pwf-checkbox-v1"
        metadata.parent.mkdir(exist_ok=True)
        metadata.symlink_to(other)
        self.assertNotEqual(self._run("--enable-checkbox-only").returncode, 0)
        self.assertTrue(metadata.is_symlink())
        self.assertEqual(other.read_bytes(), b"keep")

    @unittest.skipUnless(os.name == "posix", "checkbox mode uses POSIX descriptors")
    def test_checkbox_only_binds_plan_selection_and_strict_reapproval(self):
        for slug in ("alpha", "beta"):
            directory = self.tmp / ".planning" / slug
            directory.mkdir(parents=True)
            (directory / "task_plan.md").write_bytes(b"- [ ] one\n")
        self.assertEqual(self._run("--enable-checkbox-only", "--target", "alpha").returncode, 0)
        self.assertEqual(self._run("--target", "beta").returncode, 0)
        for slug in ("alpha", "beta"):
            (self.tmp / ".planning" / slug / "task_plan.md").write_bytes(b"- [x] one\n")
        self.assertNotEqual(self._run("--checkbox-only", "--target", "beta").returncode, 0)
        self.assertEqual(self._run("--checkbox-only", "--target", "alpha").returncode, 0)
        self.assertEqual(self._run("--target", "alpha").returncode, 0)
        self.assertNotEqual(self._run("--checkbox-only", "--target", "alpha").returncode, 0)

    @unittest.skipUnless(os.name == "posix", "checkbox mode uses POSIX descriptors")
    def test_checkbox_only_skips_code_examples(self):
        plan = self.tmp / "task_plan.md"
        old = b"~~~md\n- [ ] sample\n~~~\n    - [ ] code\n- [ ] actual\n"
        plan.write_bytes(old)
        self.assertEqual(self._run("--enable-checkbox-only").returncode, 0)
        for word in (b"sample", b"code"):
            plan.write_bytes(old.replace(b"[ ] " + word, b"[x] " + word))
            self.assertNotEqual(self._run("--checkbox-only").returncode, 0)
        plan.write_bytes(old.replace(b"[ ] actual", b"[x] actual"))
        self.assertEqual(self._run("--checkbox-only").returncode, 0)

    @unittest.skipUnless(os.name == "posix", "checkbox mode uses POSIX descriptors")
    def test_checkbox_only_requires_standalone_tasks(self):
        plan = self.tmp / "task_plan.md"
        before = (b"- parent\n  - [ ] nested\n-    [ ] padded\n*\t[ ] tab\n"
                  b"<!-- details\n- [ ] example\n-->\n- [ ] standalone\n")
        plan.write_bytes(before)
        self.assertEqual(self._run("--enable-checkbox-only").returncode, 0)
        for word in (b"nested", b"padded", b"tab", b"example"):
            plan.write_bytes(before.replace(b"[ ] " + word, b"[x] " + word))
            self.assertNotEqual(self._run("--checkbox-only").returncode, 0)
        plan.write_bytes(before.replace(b"[ ] standalone", b"[x] standalone"))
        self.assertEqual(self._run("--checkbox-only").returncode, 0)
        plan.write_bytes(b"<pre>\n- [ ] example\n</pre>\n")
        self.assertNotEqual(self._run("--enable-checkbox-only").returncode, 0)

    @unittest.skipUnless(os.name == "posix", "checkbox mode uses POSIX descriptors")
    def test_checkbox_only_fence_context_and_bom_offsets(self):
        plan = self.tmp / "task_plan.md"
        bom = bytes.fromhex("efbbbf")
        fence = b"`" * 3
        for prefix in (bom, b"    " + fence + b"\n", fence + b"lang`bad\n"):
            with self.subTest(prefix=prefix):
                before = prefix + fence + b"\n- [ ] example\n" + fence + b"\n- [ ] actual\n"
                plan.write_bytes(before)
                self.assertEqual(self._run("--enable-checkbox-only").returncode, 0)
                plan.write_bytes(before.replace(b"[ ] example", b"[x] example"))
                self.assertNotEqual(self._run("--checkbox-only").returncode, 0)
                plan.write_bytes(before.replace(b"[ ] actual", b"[x] actual"))
                self.assertEqual(self._run("--checkbox-only").returncode, 0)
        plan.write_bytes(bom + b"- [ ] first\n")
        self.assertEqual(self._run("--enable-checkbox-only").returncode, 0)
        plan.write_bytes(bom + b"- [x] first\n")
        self.assertEqual(self._run("--checkbox-only").returncode, 0)

    @unittest.skipUnless(os.name == "posix", "checkbox mode uses POSIX descriptors")
    def test_checkbox_cache_has_no_plan_text_and_is_private(self):
        plan = self.tmp / "task_plan.md"
        plan.write_bytes(b"- [ ] private content\n")
        self.assertEqual(self._run("--enable-checkbox-only").returncode, 0)
        cache = self.tmp / "home" / ".pwf-checkbox-v1"
        record, = cache.iterdir()
        self.assertEqual(cache.stat().st_mode & 0o777, 0o700)
        self.assertEqual(record.stat().st_mode & 0o777, 0o600)
        self.assertNotIn(b"private content", record.read_bytes())
        previous = (self.tmp / ".plan-attestation").read_bytes()
        record.write_bytes(b"unrelated")
        plan.write_bytes(b"- [x] private content\n")
        self.assertNotEqual(self._run("--checkbox-only").returncode, 0)
        self.assertEqual(previous, (self.tmp / ".plan-attestation").read_bytes())
        self.assertEqual(record.read_bytes(), b"unrelated")
        self.assertEqual(self._run("--clear").returncode, 0)
        self.assertFalse((self.tmp / ".plan-attestation").exists())
        self.assertEqual(record.read_bytes(), b"unrelated")

    def _checkbox_helper(self):
        # Exercise storage faults with deterministic syscall doubles. The normal
        # CLI tests above cover dispatch, selection, writer acquisition and cleanup.
        script = SCRIPT.read_text(encoding="utf-8")
        code = script.split("<<'PWF_CHECKBOX_PY'\n", 1)[1].split("\nPWF_CHECKBOX_PY", 1)[0]
        # Shell dispatch enters the physical plan directory before invoking Python.
        physical_plan = self.tmp.resolve() / "task_plan.md"
        argv = ["checkbox", "checkbox-only", str(physical_plan), ".plan-attestation"]
        with mock.patch.object(sys, "argv", argv), mock.patch.dict(os.environ, HOME=str(self.tmp / "home")):
            exec(compile(code, "<checkbox helper>", "exec"), {"__name__": "__main__"})

    @unittest.skipUnless(os.name == "posix", "checkbox mode uses POSIX descriptors")
    def test_checkbox_storage_failures_remain_retryable(self):
        plan = self.tmp / "task_plan.md"
        previous = b"- [ ] task\n"
        for failure in ("cache", "digest"):
            with self.subTest(failure=failure):
                plan.write_bytes(previous)
                self.assertEqual(self._run("--enable-checkbox-only").returncode, 0)
                plan.write_bytes(b"- [x] task\n")
                replace = os.replace
                def fail_write(src, dest, **kwargs):
                    is_digest = dest == ".plan-attestation"
                    if is_digest == (failure == "digest"):
                        raise OSError("simulated storage failure")
                    return replace(src, dest, **kwargs)
                with mock.patch("os.replace", side_effect=fail_write), self.assertRaisesRegex(
                        SystemExit, "simulated storage failure"):
                    self._checkbox_helper()
                self.assertEqual((self.tmp / ".plan-attestation").read_text().strip(),
                                 hashlib.sha256(previous).hexdigest())
                self.assertEqual(self._run("--checkbox-only").returncode, 0)

    @unittest.skipUnless(os.name == "posix", "checkbox mode uses POSIX descriptors")
    def test_checkbox_success_rechecks_plan_generation(self):
        plan = self.tmp / "task_plan.md"
        for checked, changed_at in ((False, 1), (True, 3)):
            with self.subTest(checked=checked):
                plan.write_bytes(b"- [ ] task\n")
                self.assertEqual(self._run("--enable-checkbox-only").returncode, 0)
                if checked:
                    plan.write_bytes(b"- [x] task\n")
                real_stat = os.stat
                seen = 0
                def changed_generation(path, *args, **kwargs):
                    nonlocal seen
                    result = real_stat(path, *args, **kwargs)
                    if path == "task_plan.md" and "dir_fd" in kwargs:
                        seen += 1
                        if seen == changed_at:
                            return mock.Mock(st_dev=result.st_dev, st_ino=result.st_ino,
                                             st_ctime_ns=result.st_ctime_ns + 1)
                    return result
                with mock.patch("os.stat", side_effect=changed_generation), self.assertRaisesRegex(
                        SystemExit, "Plan changed during attestation"):
                    self._checkbox_helper()
                self.assertEqual(seen, changed_at)
                self.assertEqual(self._run("--checkbox-only").returncode, 0)

    def sha256_of(self, path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

if __name__ == "__main__":
    unittest.main()
