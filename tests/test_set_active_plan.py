"""Tests for scripts/set-active-plan.sh — companion to resolve-plan-dir.sh.

set-active-plan.sh lets users explicitly switch the active plan pointer
without needing to export PLAN_ID. This is the UX complement to slug-mode
init-session.sh for parallel multi-task workflows (#148).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SET_ACTIVE_SH = REPO_ROOT / "scripts" / "set-active-plan.sh"
SET_ACTIVE_PS1 = REPO_ROOT / "scripts" / "set-active-plan.ps1"
RESOLVE_SH = REPO_ROOT / "scripts" / "resolve-plan-dir.sh"
POWERSHELL = shutil.which("powershell.exe") or shutil.which("powershell")
SH = shutil.which("sh")


def run_set_active(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["sh", str(SET_ACTIVE_SH), *args],
        cwd=str(cwd),
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )


class SetActivePlanTests(unittest.TestCase):

    def test_script_exists(self) -> None:
        self.assertTrue(SET_ACTIVE_SH.exists(), "scripts/set-active-plan.sh missing")

    def test_powershell_script_is_ascii_safe_for_windows_powershell_5(self) -> None:
        """UTF-8 without a BOM must not become invalid Windows PowerShell syntax."""
        self.assertTrue(SET_ACTIVE_PS1.exists(), "scripts/set-active-plan.ps1 missing")
        try:
            SET_ACTIVE_PS1.read_bytes().decode("ascii")
        except UnicodeDecodeError as error:
            self.fail(
                "set-active-plan.ps1 must stay ASCII-safe because Windows PowerShell 5.1 "
                f"can decode BOM-less UTF-8 as the active ANSI code page: {error}"
            )

    def test_powershell_replace_uses_a_caller_owned_backup(self) -> None:
        source = SET_ACTIVE_PS1.read_text(encoding="ascii")
        self.assertIn(
            "[IO.File]::Replace($tempFile, $ActiveFile, $backupFile)",
            source,
        )
        self.assertIn(".replace-backup", source)
        self.assertNotIn("[NullString]::Value", source)

    @unittest.skipUnless(
        POWERSHELL and os.name == "nt",
        "requires native Windows PowerShell replacement semantics",
    )
    def test_final_replace_failure_restores_owned_backup_without_glob_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "project"
            root.mkdir()
            scripts = base / "scripts"
            scripts.mkdir()

            source = SET_ACTIVE_PS1.read_text(encoding="ascii")
            needle = "[IO.File]::Replace($tempFile, $ActiveFile, $backupFile)"
            self.assertEqual(1, source.count(needle))
            injected = source.replace(
                needle,
                "[IO.File]::Move($ActiveFile, $backupFile)\n"
                "                throw [IO.IOException]::new(\"injected final replacement failure\")",
            )
            selector = scripts / "set-active-plan.ps1"
            selector.write_text(injected, encoding="ascii", newline="\n")

            planning = root / ".planning"
            old_plan = planning / "old-plan"
            new_plan = planning / "new-plan"
            old_plan.mkdir(parents=True)
            new_plan.mkdir()
            (old_plan / "task_plan.md").write_text("# old\n", encoding="utf-8")
            (new_plan / "task_plan.md").write_text("# new\n", encoding="utf-8")
            pointer = planning / ".active_plan"
            pointer.write_text("old-plan", encoding="utf-8")
            foreign_rf = planning / ".active_plan~RFKEEP.TMP"
            foreign_rf.write_bytes(b"foreign-owner")

            result = subprocess.run(
                [
                    POWERSHELL,
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(selector),
                    "new-plan",
                ],
                cwd=str(root),
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertIn("injected final replacement failure", result.stderr)
            self.assertEqual(b"old-plan", pointer.read_bytes())
            self.assertEqual(b"foreign-owner", foreign_rf.read_bytes())
            self.assertEqual([], list(planning.glob(".active_plan.*.replace-backup")))
            self.assertEqual([], list(planning.glob(".active_plan.*.tmp")))

    @unittest.skipUnless(
        POWERSHELL and os.name == "nt",
        "requires native Windows PowerShell replacement semantics",
    )
    def test_held_backup_after_successful_replace_still_reports_success(self) -> None:
        # After a successful Replace the owned backup only holds the superseded
        # pointer. When it cannot be deleted (here the selector itself keeps it
        # open without delete sharing), the new pointer is already in place, so
        # the call must warn and succeed rather than report a failed switch.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "project"
            root.mkdir()
            scripts = base / "scripts"
            scripts.mkdir()

            source = SET_ACTIVE_PS1.read_text(encoding="ascii")
            needle = "[IO.File]::Replace($tempFile, $ActiveFile, $backupFile)"
            self.assertEqual(1, source.count(needle))
            injected = source.replace(
                needle,
                needle + "\n"
                "                $script:heldBackup = [IO.File]::Open($backupFile, 'Open', 'Read', 'Read')",
            )
            selector = scripts / "set-active-plan.ps1"
            selector.write_text(injected, encoding="ascii", newline="\n")

            planning = root / ".planning"
            old_plan = planning / "old-plan"
            new_plan = planning / "new-plan"
            old_plan.mkdir(parents=True)
            new_plan.mkdir()
            (old_plan / "task_plan.md").write_text("# old\n", encoding="utf-8")
            (new_plan / "task_plan.md").write_text("# new\n", encoding="utf-8")
            pointer = planning / ".active_plan"
            pointer.write_text("old-plan", encoding="utf-8")

            result = subprocess.run(
                [
                    POWERSHELL,
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(selector),
                    "new-plan",
                ],
                cwd=str(root),
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                check=False,
            )

            output = result.stdout + result.stderr
            self.assertEqual(0, result.returncode, output)
            self.assertIn("Active plan set to: new-plan", result.stdout)
            self.assertIn("could not remove the replacement backup", output)
            self.assertEqual(b"new-plan", pointer.read_bytes())
            backups = list(planning.glob(".active_plan.*.replace-backup"))
            self.assertEqual(1, len(backups))
            self.assertEqual(b"old-plan", backups[0].read_bytes())
            self.assertEqual([], list(planning.glob(".active_plan.*.tmp")))

    @unittest.skipUnless(
        POWERSHELL and SH,
        "requires Windows PowerShell and sh for the cross-shell regression test",
    )
    def test_powershell_pointer_is_utf8_without_bom_and_resolves(self) -> None:
        """The PS 5.1 writer must not add a BOM that the shell resolver rejects."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            selected = root / ".planning" / "selected"
            newest = root / ".planning" / "newest"
            selected.mkdir(parents=True)
            newest.mkdir(parents=True)
            (selected / "task_plan.md").write_text("# Selected\n", encoding="utf-8")
            (newest / "task_plan.md").write_text("# Newest\n", encoding="utf-8")
            selected_mtime = selected.stat().st_mtime
            os.utime(newest, (selected_mtime + 10, selected_mtime + 10))

            written = subprocess.run(
                [
                    POWERSHELL,
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(SET_ACTIVE_PS1),
                    "selected",
                ],
                cwd=str(root),
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, written.returncode, written.stderr)
            self.assertEqual(
                b"selected",
                (root / ".planning" / ".active_plan").read_bytes(),
            )

            resolved = subprocess.run(
                [SH, str(RESOLVE_SH)],
                cwd=str(root),
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, resolved.returncode, resolved.stderr)
            self.assertEqual("", resolved.stdout.strip())
            # Pointer bytes are still portable; only single-plan discovery
            # may use them without an explicit session pin.
            (newest / "task_plan.md").unlink()
            single = subprocess.run(
                [SH, str(RESOLVE_SH)], cwd=str(root), text=True,
                encoding="utf-8", capture_output=True, check=False,
            )
            self.assertTrue(single.stdout.strip().endswith("selected"))

    def test_no_args_no_active_plan_prints_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run_set_active(Path(tmp))
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("No active plan", result.stdout)

    def test_no_args_shows_current_active_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = root / ".planning" / "2026-01-10-my-task"
            plan.mkdir(parents=True)
            (root / ".planning" / ".active_plan").write_text("2026-01-10-my-task\n", encoding="utf-8")
            result = run_set_active(root)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("2026-01-10-my-task", result.stdout)

    def test_list_plans_shows_available_plans_status_and_active_marker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            planning = root / ".planning"
            active = planning / "2026-01-10-active"
            other = planning / "2026-01-11-other"
            hidden = planning / ".scratch"
            active.mkdir(parents=True)
            other.mkdir(parents=True)
            hidden.mkdir(parents=True)
            (active / "task_plan.md").write_text(
                "# Active\n\n"
                "### Phase 1\n- **Status:** complete\n"
                "### Phase 2\n- **Status:** in_progress\n",
                encoding="utf-8",
            )
            (other / "task_plan.md").write_text(
                "# Other\n\n"
                "### Phase 1 [complete]\n"
                "### Phase 2 [pending]\n",
                encoding="utf-8",
            )
            (hidden / "task_plan.md").write_text("# Hidden\n", encoding="utf-8")
            (planning / ".active_plan").write_text("2026-01-10-active\n", encoding="utf-8")

            result = run_set_active(root, "--list")

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("Available plans:", result.stdout)
            self.assertIn("2026-01-10-active [active]", result.stdout)
            self.assertIn("1/2 complete, 1 in_progress, 0 pending", result.stdout)
            self.assertIn("2026-01-11-other", result.stdout)
            self.assertIn("1/2 complete, 0 in_progress, 1 pending", result.stdout)
            self.assertNotIn(".scratch", result.stdout)

    def test_list_plans_without_planning_dir_is_clean(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run_set_active(Path(tmp), "--list")
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("No planning directory found", result.stdout)

    def test_sets_active_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan_a = root / ".planning" / "task-a"
            plan_b = root / ".planning" / "task-b"
            plan_a.mkdir(parents=True)
            plan_b.mkdir(parents=True)
            # Set to task-a first
            r1 = run_set_active(root, "task-a")
            self.assertEqual(0, r1.returncode, r1.stderr)
            active = (root / ".planning" / ".active_plan").read_text(encoding="utf-8").strip()
            self.assertEqual("task-a", active)
            # Switch to task-b
            r2 = run_set_active(root, "task-b")
            self.assertEqual(0, r2.returncode, r2.stderr)
            active = (root / ".planning" / ".active_plan").read_text(encoding="utf-8").strip()
            self.assertEqual("task-b", active)

    def test_linked_plan_directory_is_refused_and_not_listed(self) -> None:
        # #270: no route selects a symlinked or junctioned plan directory, so the
        # pointer tool must neither advertise one nor point the shared default at it.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            real = root / ".planning" / "2026-01-10-real"
            real.mkdir(parents=True)
            (real / "task_plan.md").write_text("# Real\n\n### Phase 1\n- **Status:** in_progress\n", encoding="utf-8")
            target = root / "linked-target"
            target.mkdir()
            (target / "task_plan.md").write_text("# Linked\n\n### Phase 1\n- **Status:** complete\n", encoding="utf-8")
            link = root / ".planning" / "2026-01-11-linked"
            if os.name == "nt":
                made = subprocess.run(["cmd", "/d", "/c", "mklink", "/J", str(link), str(target)],
                                      capture_output=True, text=True, check=False)
                if made.returncode != 0:
                    self.skipTest("junction creation unavailable: " + made.stderr.strip())
            else:
                try:
                    link.symlink_to(target, target_is_directory=True)
                except OSError as exc:
                    self.skipTest(f"symlink creation unavailable: {exc}")
            listed = run_set_active(root, "--list")
            self.assertEqual(0, listed.returncode, listed.stderr)
            self.assertIn("2026-01-10-real", listed.stdout)
            self.assertNotIn("2026-01-11-linked", listed.stdout)
            refused = run_set_active(root, "2026-01-11-linked")
            self.assertNotEqual(0, refused.returncode)
            self.assertIn("symlink or junction", refused.stderr)
            self.assertFalse((root / ".planning" / ".active_plan").exists())
            accepted = run_set_active(root, "2026-01-10-real")
            self.assertEqual(0, accepted.returncode, accepted.stderr)
            if POWERSHELL:
                def run_ps(*args: str) -> subprocess.CompletedProcess[str]:
                    return subprocess.run(
                        [POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(SET_ACTIVE_PS1), *args],
                        cwd=str(root), text=True, encoding="utf-8", capture_output=True, check=False,
                    )
                ps_listed = run_ps("--list")
                self.assertEqual(0, ps_listed.returncode, ps_listed.stderr)
                self.assertIn("2026-01-10-real", ps_listed.stdout)
                self.assertNotIn("2026-01-11-linked", ps_listed.stdout)
                ps_refused = run_ps("2026-01-11-linked")
                self.assertNotEqual(0, ps_refused.returncode)
                # Windows PowerShell 5.1 wraps stderr at the console width
                flat = " ".join((ps_refused.stderr + ps_refused.stdout).split())
                self.assertIn("symlink or junction", flat)
                self.assertEqual(
                    "2026-01-10-real",
                    (root / ".planning" / ".active_plan").read_text(encoding="utf-8").strip(),
                    "a refused selection must leave the pointer untouched",
                )

    @unittest.skipUnless(POWERSHELL, "requires PowerShell")
    def test_powershell_pointer_safety_is_linktype_not_reparse_attribute(self) -> None:
        # #275: a symlinked pointer is refused by the resolver and by the writer;
        # a plain pointer resolves and can be rewritten. The ReparsePoint
        # attribute, which OneDrive Files On-Demand sets on every synced file,
        # is no longer what decides.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # one named plan: two would trip the several-plans rule (#240) before the pointer matters
            (root / ".planning" / "2026-01-10-alpha").mkdir(parents=True)
            (root / ".planning" / "2026-01-10-alpha" / "task_plan.md").write_text("# alpha\n", encoding="utf-8")
            pointer = root / ".planning" / ".active_plan"

            def run_ps(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
                return subprocess.run(
                    [POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), *args],
                    cwd=str(root), text=True, encoding="utf-8", capture_output=True, check=False,
                )

            written = run_ps(SET_ACTIVE_PS1, "2026-01-10-alpha")
            self.assertEqual(0, written.returncode, written.stderr)
            resolved = run_ps(REPO_ROOT / "scripts" / "resolve-plan-dir.ps1")
            self.assertTrue(resolved.stdout.strip().endswith("2026-01-10-alpha"), resolved.stdout)
            outside = root / "elsewhere.txt"
            outside.write_text("2026-01-11-beta\n", encoding="utf-8")
            pointer.unlink()
            try:
                pointer.symlink_to(outside)
            except OSError as exc:
                self.skipTest(f"file symlinks are unavailable: {exc}")
            try:
                linked = run_ps(REPO_ROOT / "scripts" / "resolve-plan-dir.ps1")
                self.assertEqual(0, linked.returncode, linked.stderr)
                self.assertEqual("", linked.stdout.strip(), "a symlinked pointer must stop resolution")
                refused = run_ps(SET_ACTIVE_PS1, "2026-01-10-alpha")
                self.assertNotEqual(0, refused.returncode)
                self.assertTrue(pointer.is_symlink(), "a refused write must leave the symlink alone")
                self.assertEqual("2026-01-11-beta\n", outside.read_text(encoding="utf-8"))
            finally:
                pointer.unlink()

    def test_errors_on_nonexistent_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_set_active(root, "ghost-plan")
            self.assertNotEqual(0, result.returncode)
            self.assertIn("not found", result.stderr)

    def test_shared_pointer_changes_do_not_bind_multiple_plans(self) -> None:
        # Writing a shared pointer does not bind any individual session.
        from pathlib import Path as P
        resolve_sh = REPO_ROOT / "scripts" / "resolve-plan-dir.sh"
        with tempfile.TemporaryDirectory() as tmp:
            root = P(tmp)
            plan_a = root / ".planning" / "2026-task-a"
            plan_b = root / ".planning" / "2026-task-b"
            plan_a.mkdir(parents=True)
            plan_b.mkdir(parents=True)
            (plan_a / "task_plan.md").write_text("# A\n", encoding="utf-8")
            (plan_b / "task_plan.md").write_text("# B\n", encoding="utf-8")
            # Set the shared pointer to task-a.
            run_set_active(root, "2026-task-a")
            result = subprocess.run(
                ["sh", str(resolve_sh)],
                cwd=str(root),
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=False,
            )
            self.assertEqual("", result.stdout.strip())
            # Switch to task-b
            run_set_active(root, "2026-task-b")
            result = subprocess.run(
                ["sh", str(resolve_sh)],
                cwd=str(root),
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=False,
            )
            self.assertEqual("", result.stdout.strip())
            pinned = subprocess.run(
                ["sh", str(resolve_sh)], cwd=str(root), text=True,
                encoding="utf-8", capture_output=True, check=False,
                env=dict(os.environ, PLAN_ID="2026-task-a"),
            )
            self.assertTrue(pinned.stdout.strip().endswith("2026-task-a"))


if __name__ == "__main__":
    unittest.main()
