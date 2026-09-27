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


if __name__ == "__main__":
    unittest.main()
