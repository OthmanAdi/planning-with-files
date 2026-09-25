"""Windows PowerShell parity tests for slug-aware init-session.ps1."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
import os
from datetime import date
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INIT_PS1 = REPO_ROOT / "scripts" / "init-session.ps1"
POWERSHELL = shutil.which("powershell") or shutil.which("powershell.exe")
PWSH = shutil.which("pwsh") or shutil.which("pwsh.exe")
ICACLS = shutil.which("icacls") or shutil.which("icacls.exe")


def flat(text: str) -> str:
    # Windows PowerShell 5.1 wraps error records at the console width, which
    # can split a phrase across lines; compare on collapsed whitespace.
    return " ".join(text.split())


def child_env() -> dict[str, str]:
    """A developer's PWF_PLAN_ROOT pin must not redirect the initializer under test."""
    return {key: value for key, value in os.environ.items() if key != "PWF_PLAN_ROOT"}


@unittest.skipUnless(POWERSHELL, "requires Windows PowerShell")
class InitSessionPowerShellSlugTests(unittest.TestCase):
    def run_init(self, cwd: Path, *args: str, shell: str | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                shell or POWERSHELL,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(INIT_PS1),
                *args,
            ],
            cwd=str(cwd),
            text=True,
            encoding="utf-8-sig",
            capture_output=True,
            check=False,
            env=child_env(),
        )

    def test_named_plan_creates_dated_slug_directory_and_active_pointer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self.run_init(root, "Backend Refactor")
            self.assertEqual(0, result.returncode, result.stderr)

            plan_id = f"{date.today().isoformat()}-backend-refactor"
            plan_dir = root / ".planning" / plan_id
            self.assertTrue((plan_dir / "task_plan.md").is_file())
            self.assertTrue((plan_dir / "findings.md").is_file())
            self.assertTrue((plan_dir / "progress.md").is_file())
            self.assertFalse((root / "task_plan.md").exists())
            active = (root / ".planning" / ".active_plan").read_text(encoding="utf-8-sig").strip()
            self.assertEqual(plan_id, active)

    def test_zero_args_preserves_legacy_root_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self.run_init(root)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue((root / "task_plan.md").is_file())
            self.assertTrue((root / "findings.md").is_file())
            self.assertTrue((root / "progress.md").is_file())
            self.assertFalse((root / ".planning").exists())
            self.assertIn("Created task_plan.md", result.stdout)
            self.assertIn("Created findings.md", result.stdout)
            self.assertIn("Created progress.md", result.stdout)

    def test_plan_dir_without_name_uses_untitled_slug(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self.run_init(root, "-PlanDir")
            self.assertEqual(0, result.returncode, result.stderr)
            dirs = [p for p in (root / ".planning").iterdir() if p.is_dir()]
            self.assertEqual(1, len(dirs))
            self.assertRegex(
                dirs[0].name,
                rf"^{date.today().isoformat()}-untitled-[a-f0-9]{{8}}$",
            )

    def test_slug_sanitizes_unsafe_characters(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self.run_init(root, "Foo / Bar! Baz??")
            self.assertEqual(0, result.returncode, result.stderr)
            expected = root / ".planning" / f"{date.today().isoformat()}-foo-bar-baz"
            self.assertTrue(expected.is_dir())

    def test_slug_collision_appends_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = self.run_init(root, "same name")
            second = self.run_init(root, "same name")
            self.assertEqual(0, first.returncode, first.stderr)
            self.assertEqual(0, second.returncode, second.stderr)
            today = date.today().isoformat()
            self.assertTrue((root / ".planning" / f"{today}-same-name").is_dir())
            self.assertTrue((root / ".planning" / f"{today}-same-name-2").is_dir())

    def test_slug_plan_inherits_root_gated_mode_and_is_attested(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".mode").write_text("autonomous gate\n", encoding="ascii")
            result = self.run_init(root, "Child Plan")
            self.assertEqual(0, result.returncode, result.stderr)
            plan_dir = root / ".planning" / f"{date.today().isoformat()}-child-plan"
            self.assertEqual(
                "autonomous gate",
                (plan_dir / ".mode").read_text(encoding="ascii").strip(),
            )
            self.assertEqual("0", (plan_dir / ".stop_blocks").read_text(encoding="ascii").strip())
            self.assertRegex((plan_dir / ".nonce").read_text(encoding="ascii"), r"^[a-f0-9]{16}$")
            self.assertTrue((plan_dir / ".attestation").is_file())

    def test_named_plan_preserves_template_selection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self.run_init(root, "-Template", "analytics", "Analytics Run")
            self.assertEqual(0, result.returncode, result.stderr)
            plan_dir = root / ".planning" / f"{date.today().isoformat()}-analytics-run"
            expected = (REPO_ROOT / "templates" / "analytics_task_plan.md").read_bytes()
            self.assertEqual(expected, (plan_dir / "task_plan.md").read_bytes())

    def test_named_autonomous_plan_writes_mode_and_attestation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self.run_init(root, "-Autonomous", "Auto Plan")
            self.assertEqual(0, result.returncode, result.stderr)
            plan_dir = root / ".planning" / f"{date.today().isoformat()}-auto-plan"
            self.assertEqual(
                "autonomous",
                (plan_dir / ".mode").read_text(encoding="ascii").strip(),
            )
            self.assertTrue((plan_dir / ".attestation").is_file())

    def test_named_autonomous_plan_attests_current_project_despite_stale_plan_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as other_tmp:
            root = Path(tmp)
            other = Path(other_tmp)
            env = child_env()
            env["PWF_PLAN_ROOT"] = str(other)
            result = subprocess.run(
                [POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(INIT_PS1), "-Autonomous", "Bound Root"],
                cwd=str(root), text=True, encoding="utf-8-sig", capture_output=True,
                env=env, check=False,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            plan_dir = root / ".planning" / f"{date.today().isoformat()}-bound-root"
            self.assertTrue((plan_dir / ".attestation").is_file())

    def test_root_autonomous_plan_attests_the_root_plan(self) -> None:
        # Root mode attests the root task_plan.md through the attester's legacy
        # fallback, which only runs when no selector is set; binding
        # PWF_PLAN_ROOT here (as slug mode does) makes the attester refuse it.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self.run_init(root, "-Autonomous")
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertFalse((root / ".planning").exists())
            self.assertEqual("autonomous", (root / ".mode").read_text(encoding="utf-8").strip())
            self.assertTrue((root / ".plan-attestation").is_file(), "root mode must attest task_plan.md")

    def test_root_gated_plan_attests_the_root_plan_despite_inherited_pin_and_plan_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as other_tmp:
            root = Path(tmp)
            other = Path(other_tmp)
            (other / "task_plan.md").write_text("# Other project\n", encoding="utf-8")
            env = child_env()
            env["PWF_PLAN_ROOT"] = str(other)
            env["PLAN_ID"] = "2026-01-01-sibling"
            result = subprocess.run(
                [POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(INIT_PS1), "-Gated"],
                cwd=str(root), text=True, encoding="utf-8-sig", capture_output=True,
                env=env, check=False,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual("autonomous gate", (root / ".mode").read_text(encoding="utf-8").strip())
            self.assertTrue((root / ".plan-attestation").is_file())
            self.assertFalse((other / ".plan-attestation").exists())

    def test_named_autonomous_plan_attests_new_plan_despite_stale_plan_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            previous = os.environ.get("PLAN_ID")
            os.environ["PLAN_ID"] = "stale-plan-id"
            try:
                result = self.run_init(root, "-Autonomous", "Bound Plan")
            finally:
                if previous is None:
                    os.environ.pop("PLAN_ID", None)
                else:
                    os.environ["PLAN_ID"] = previous

            self.assertEqual(0, result.returncode, result.stderr)
            plan_dir = root / ".planning" / f"{date.today().isoformat()}-bound-plan"
            self.assertTrue((plan_dir / ".attestation").is_file())

    # Pointer safety mirrors tests/test_init_session_slug.py for init-session.sh:
    # the shared pointer is replaced through set-active-plan.ps1, never written
    # in place, and the planning root is verified before anything is created.
    def test_slug_init_replaces_hardlinked_pointer_without_mutating_peer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            planning = root / ".planning"
            planning.mkdir()
            sentinel = root / "sentinel.txt"
            sentinel.write_bytes(b"KEEP-ME")
            pointer = planning / ".active_plan"
            os.link(sentinel, pointer)

            result = self.run_init(root, "Hardlink Test")

            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertEqual(b"KEEP-ME", sentinel.read_bytes())
            expected = f"{date.today().isoformat()}-hardlink-test"
            self.assertEqual(expected, pointer.read_text(encoding="utf-8-sig").strip())

    @unittest.skipUnless(os.name == "nt", "requires Windows read-only file attributes")
    @unittest.skipUnless(os.name == "nt", "requires Windows read-only file attributes")
    def test_slug_init_rejects_readonly_pointer_before_creating_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = self.run_init(root, "First")
            self.assertEqual(0, first.returncode, first.stdout + first.stderr)
            pointer = root / ".planning" / ".active_plan"
            readonly = subprocess.run(
                [
                    POWERSHELL,
                    "-NoProfile",
                    "-Command",
                    "(Get-Item -LiteralPath '.planning\\.active_plan').IsReadOnly=$true",
                ],
                cwd=str(root), text=True, encoding="utf-8-sig",
                capture_output=True, check=False, env=child_env(),
            )
            self.assertEqual(0, readonly.returncode, readonly.stdout + readonly.stderr)
            try:
                result = self.run_init(root, "Second")
                self.assertNotEqual(0, result.returncode, result.stdout + result.stderr)
                self.assertIn("active plan pointer", flat(result.stderr))
                self.assertFalse((root / ".planning" / f"{date.today().isoformat()}-second").exists())
            finally:
                subprocess.run(
                    [
                        POWERSHELL,
                        "-NoProfile",
                        "-Command",
                        "(Get-Item -LiteralPath '.planning\\.active_plan').IsReadOnly=$false",
                    ],
                    cwd=str(root), text=True, encoding="utf-8-sig",
                    capture_output=True, check=False, env=child_env(),
                )

    def test_slug_init_rejects_symlink_pointer_without_following_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            planning = root / ".planning"
            planning.mkdir()
            sentinel = root / "sentinel.txt"
            sentinel.write_bytes(b"KEEP-ME")
            pointer = planning / ".active_plan"
            try:
                pointer.symlink_to(sentinel)
            except (OSError, NotImplementedError) as error:
                self.skipTest(f"file symlinks unavailable: {error}")

            result = self.run_init(root, "Symlink Test")

            self.assertNotEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertEqual(b"KEEP-ME", sentinel.read_bytes())
            self.assertTrue(pointer.is_symlink())
            self.assertIn("active plan pointer", flat(result.stderr))

    def test_slug_init_refuses_unsafe_pointer_before_creating_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            planning = root / ".planning"
            (planning / ".active_plan").mkdir(parents=True)

            result = self.run_init(root, "Dir Pointer")

            self.assertNotEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertIn("active plan pointer", flat(result.stderr))
            self.assertEqual([".active_plan"], sorted(p.name for p in planning.iterdir()))

    def test_slug_init_rejects_external_planning_directory_before_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside_tmp:
            root = Path(tmp)
            outside = Path(outside_tmp)
            planning = root / ".planning"
            try:
                planning.symlink_to(outside, target_is_directory=True)
            except (OSError, NotImplementedError) as error:
                junction = subprocess.run(
                    ["cmd.exe", "/d", "/c", "mklink", "/J", str(planning), str(outside)],
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    capture_output=True,
                    check=False,
                )
                if junction.returncode != 0:
                    self.skipTest(
                        f"directory links unavailable: {error}; {junction.stdout}{junction.stderr}"
                    )

            result = self.run_init(root, "Escaped Plan")

            self.assertNotEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertEqual([], list(outside.iterdir()))
            self.assertIn("outside the project", flat(result.stderr))

    def test_concurrent_named_inits_all_replace_pointer_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            processes = [
                subprocess.Popen(
                    [
                        POWERSHELL,
                        "-NoProfile",
                        "-ExecutionPolicy",
                        "Bypass",
                        "-File",
                        str(INIT_PS1),
                        f"Race Case {index}",
                    ],
                    cwd=str(root), text=True, encoding="utf-8-sig",
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=child_env(),
                )
                for index in range(4)
            ]
            results = [process.communicate(timeout=30) + (process.returncode,) for process in processes]
            for stdout, stderr, returncode in results:
                self.assertEqual(0, returncode, stdout + stderr)
            planning = root / ".planning"
            self.assertTrue((planning / ".active_plan").is_file())
            self.assertEqual([], list(planning.glob(".active_plan~RF*.TMP")))
            self.assertEqual([], list(planning.glob(".active_plan.*.replace-backup")))
            self.assertEqual([], list(planning.glob(".active_plan.*.tmp")))

    def test_transient_pointer_inspection_retries_after_root_verification(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "project"
            root.mkdir()
            scripts = base / "skill" / "scripts"
            scripts.mkdir(parents=True)
            shutil.copy2(INIT_PS1, scripts / "init-session.ps1")
            shutil.copy2(REPO_ROOT / "scripts" / "set-active-plan.ps1",
                         scripts / "set-active-plan-real.ps1")
            (scripts / "set-active-plan.ps1").write_text(
                r"""
param([string]$PlanId = "", [switch]$VerifyRoot)
$real = Join-Path $PSScriptRoot 'set-active-plan-real.ps1'
if ($VerifyRoot) { & $real -VerifyRoot *> $null; exit $LASTEXITCODE }
$marker = Join-Path (Get-Location).Path 'attempts.txt'
if (-not (Test-Path -LiteralPath $marker)) {
    [IO.File]::WriteAllText($marker, '1')
    Write-Error 'Error: could not set the active plan pointer: the active plan pointer became unsafe during replacement'
    exit 1
}
[IO.File]::AppendAllText($marker, '2')
& $real $PlanId *> $null
exit $LASTEXITCODE
""",
                encoding="ascii",
            )

            result = subprocess.run(
                [POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass",
                 "-File", str(scripts / "init-session.ps1"), "Retry Case"],
                cwd=root, text=True, encoding="utf-8-sig",
                capture_output=True, check=False, env=child_env(),
            )

            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertEqual("12", (root / "attempts.txt").read_text(encoding="ascii"))
            expected = f"{date.today().isoformat()}-retry-case"
            self.assertEqual(expected, (root / ".planning" / ".active_plan").read_text())

    def test_pointer_precheck_race_retries_after_root_verification(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "project"
            root.mkdir()
            scripts = base / "skill" / "scripts"
            scripts.mkdir(parents=True)
            shutil.copy2(INIT_PS1, scripts / "init-session.ps1")
            shutil.copy2(REPO_ROOT / "scripts" / "set-active-plan.ps1",
                         scripts / "set-active-plan-real.ps1")
            (scripts / "set-active-plan.ps1").write_text(
                r"""
param([string]$PlanId = "", [switch]$VerifyRoot)
$real = Join-Path $PSScriptRoot 'set-active-plan-real.ps1'
if ($VerifyRoot) { & $real -VerifyRoot *> $null; exit $LASTEXITCODE }
$marker = Join-Path (Get-Location).Path 'precheck-attempts.txt'
if (-not (Test-Path -LiteralPath $marker)) {
    [IO.File]::WriteAllText($marker, '1')
    Write-Error 'Error: the active plan pointer must be a regular file within the project.'
    exit 1
}
[IO.File]::AppendAllText($marker, '2')
& $real $PlanId *> $null
exit $LASTEXITCODE
""",
                encoding="ascii",
            )

            result = subprocess.run(
                [POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass",
                 "-File", str(scripts / "init-session.ps1"), "Precheck Retry"],
                cwd=root, text=True, encoding="utf-8-sig",
                capture_output=True, check=False, env=child_env(),
            )

            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertEqual(
                "12", (root / "precheck-attempts.txt").read_text(encoding="ascii")
            )
            expected = f"{date.today().isoformat()}-precheck-retry"
            self.assertEqual(expected, (root / ".planning" / ".active_plan").read_text())

    def test_pointer_retry_stops_when_pointer_becomes_readonly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "project"
            root.mkdir()
            scripts = base / "skill" / "scripts"
            scripts.mkdir(parents=True)
            shutil.copy2(INIT_PS1, scripts / "init-session.ps1")
            shutil.copy2(REPO_ROOT / "scripts" / "set-active-plan.ps1",
                         scripts / "set-active-plan-real.ps1")
            (scripts / "set-active-plan.ps1").write_text(
                r"""
param([string]$PlanId = "", [switch]$VerifyRoot)
$real = Join-Path $PSScriptRoot 'set-active-plan-real.ps1'
if ($VerifyRoot) { & $real -VerifyRoot *> $null; exit $LASTEXITCODE }
$marker = Join-Path (Get-Location).Path 'attempts.txt'
if (-not (Test-Path -LiteralPath $marker)) {
    [IO.File]::WriteAllText($marker, '1')
    $pointer = Join-Path (Join-Path (Get-Location).Path '.planning') '.active_plan'
    [IO.File]::WriteAllText($pointer, 'KEEP')
    (Get-Item -LiteralPath $pointer).IsReadOnly = $true
    Write-Error 'Error: could not set the active plan pointer: the active plan pointer became unsafe during replacement'
    exit 1
}
[IO.File]::AppendAllText($marker, '2')
& $real $PlanId *> $null
exit $LASTEXITCODE
""",
                encoding="ascii",
            )
            pointer = root / ".planning" / ".active_plan"
            try:
                result = subprocess.run(
                    [POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass",
                     "-File", str(scripts / "init-session.ps1"), "Readonly Race"],
                    cwd=root, text=True, encoding="utf-8-sig",
                    capture_output=True, check=False, env=child_env(),
                )
                self.assertNotEqual(0, result.returncode, result.stdout + result.stderr)
                self.assertEqual("1", (root / "attempts.txt").read_text(encoding="ascii"))
                self.assertEqual(b"KEEP", pointer.read_bytes())
            finally:
                if pointer.exists():
                    pointer.chmod(0o666)

    def test_pointer_retry_does_not_repeat_other_selector_failures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "project"
            root.mkdir()
            scripts = base / "skill" / "scripts"
            scripts.mkdir(parents=True)
            shutil.copy2(INIT_PS1, scripts / "init-session.ps1")
            shutil.copy2(REPO_ROOT / "scripts" / "set-active-plan.ps1",
                         scripts / "set-active-plan-real.ps1")
            (scripts / "set-active-plan.ps1").write_text(
                r"""
param([string]$PlanId = "", [switch]$VerifyRoot)
$real = Join-Path $PSScriptRoot 'set-active-plan-real.ps1'
if ($VerifyRoot) { & $real -VerifyRoot *> $null; exit $LASTEXITCODE }
$marker = Join-Path (Get-Location).Path 'attempts.txt'
if (-not (Test-Path -LiteralPath $marker)) {
    [IO.File]::WriteAllText($marker, '1')
    Write-Error 'Error: another selector failure'
    exit 1
}
[IO.File]::AppendAllText($marker, '2')
& $real $PlanId *> $null
exit $LASTEXITCODE
""",
                encoding="ascii",
            )

            result = subprocess.run(
                [POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass",
                 "-File", str(scripts / "init-session.ps1"), "No Retry Case"],
                cwd=root, text=True, encoding="utf-8-sig",
                capture_output=True, check=False, env=child_env(),
            )

            self.assertNotEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertEqual("1", (root / "attempts.txt").read_text(encoding="ascii"))
            self.assertFalse((root / ".planning" / ".active_plan").exists())

    def test_slug_from_non_ascii_letters_stays_ascii(self) -> None:
        # A dotted capital I survives a case-insensitive -replace; the plan id
        # must still be one the resolvers and the selector accept.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            name = chr(0x130) + "stanbul Deploy"
            result = self.run_init(root, name)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            dirs = [p.name for p in (root / ".planning").iterdir() if p.is_dir()]
            self.assertEqual(1, len(dirs), dirs)
            self.assertRegex(dirs[0], rf"^{date.today().isoformat()}-[a-z0-9-]+$")
            active = (root / ".planning" / ".active_plan").read_text(encoding="utf-8-sig").strip()
            self.assertEqual(dirs[0], active)

    def test_empty_positional_name_stays_in_root_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self.run_init(root, "")
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertTrue((root / "task_plan.md").is_file())
            self.assertFalse((root / ".planning").exists())

    def test_plan_dir_without_name_reports_untitled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self.run_init(root, "-PlanDir")
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertIn("Initializing planning files for: untitled", result.stdout)

    def test_root_mode_inheritance_is_case_sensitive(self) -> None:
        # inherit_root_mode in init-session.sh and the injector match "gate"
        # case-sensitively; an upper-case marker is not a policy floor.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".mode").write_text("GATE\n", encoding="ascii")
            result = self.run_init(root, "Upper Marker")
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            plan_dir = root / ".planning" / f"{date.today().isoformat()}-upper-marker"
            self.assertTrue((plan_dir / "task_plan.md").is_file())
            self.assertFalse((plan_dir / ".mode").exists())

    @unittest.skipUnless(os.name == "nt" and ICACLS, "requires Windows ACL tools")
    def test_denied_root_write_fails_without_success_output(self) -> None:
        shells = [POWERSHELL]
        if PWSH and Path(PWSH).resolve() != Path(POWERSHELL).resolve():
            shells.append(PWSH)

        user = subprocess.run(
            ["whoami"], text=True, encoding="utf-8", errors="replace",
            capture_output=True, check=True,
        ).stdout.strip()
        for shell in shells:
            with self.subTest(shell=Path(shell).name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                denied = subprocess.run(
                    [ICACLS, str(root), "/deny", f"{user}:(W)"],
                    text=True, encoding="utf-8", errors="replace",
                    capture_output=True, check=False,
                )
                if denied.returncode != 0:
                    self.skipTest(f"could not deny writes with icacls: {denied.stdout}{denied.stderr}")
                try:
                    result = self.run_init(root, shell=shell)
                finally:
                    restored = subprocess.run(
                        [ICACLS, str(root), "/remove:d", user],
                        text=True, encoding="utf-8", errors="replace",
                        capture_output=True, check=False,
                    )
                self.assertEqual(0, restored.returncode, restored.stdout + restored.stderr)
                self.assertNotEqual(0, result.returncode, result.stdout + result.stderr)
                self.assertNotIn("Created task_plan.md", result.stdout)
                self.assertNotIn("Planning files initialized!", result.stdout)
                for name in ("task_plan.md", "findings.md", "progress.md"):
                    self.assertFalse((root / name).exists(), name)

    def test_named_plan_write_failure_does_not_activate_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            planning = root / ".planning"
            previous_id = "2026-01-01-existing"
            previous = planning / previous_id
            previous.mkdir(parents=True)
            (previous / "task_plan.md").write_text("# Existing plan\n", encoding="utf-8")
            (planning / ".active_plan").write_text(previous_id, encoding="utf-8")

            wrapper = root / "deny-out-file.ps1"
            init_path = str(INIT_PS1).replace("'", "''")
            wrapper.write_text(
                f"""function Out-File {{
    [CmdletBinding()]
    param(
        [Parameter(ValueFromPipeline=$true)] [object] $InputObject,
        [string] $LiteralPath,
        [string] $Encoding
    )
    process {{ Write-Error "Access to the path '$LiteralPath' is denied." }}
}}
& '{init_path}' 'Denied Plan'
exit $LASTEXITCODE
""",
                encoding="utf-8-sig",
            )

            result = subprocess.run(
                [POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(wrapper)],
                cwd=str(root), text=True, encoding="utf-8-sig",
                capture_output=True, check=False, env=child_env(),
            )

            self.assertNotEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertNotIn("Created ", result.stdout)
            self.assertNotIn("Planning files initialized!", result.stdout)
            self.assertEqual(
                previous_id,
                (planning / ".active_plan").read_text(encoding="utf-8-sig").strip(),
            )
            plan_dir = planning / f"{date.today().isoformat()}-denied-plan"
            self.assertTrue(plan_dir.is_dir())
            for name in ("task_plan.md", "findings.md", "progress.md"):
                self.assertFalse((plan_dir / name).exists(), name)

    def test_windows_powershell_recovers_bracketed_project_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "proj [v2]"
            root.mkdir()
            result = self.run_init(root, "Bracket Plan")
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            plan_dir = root / ".planning" / f"{date.today().isoformat()}-bracket-plan"
            for name in ("task_plan.md", "findings.md", "progress.md"):
                self.assertTrue((plan_dir / name).is_file(), name)
            self.assertEqual(
                plan_dir.name,
                (root / ".planning" / ".active_plan").read_text(encoding="utf-8-sig").strip(),
            )

    @unittest.skipUnless(PWSH, "requires pwsh")
    def test_pwsh_writes_plan_files_inside_bracketed_project_path(self) -> None:
        # Out-File -FilePath treats [ and ] as wildcards once the path is
        # absolute; -LiteralPath keeps root mode and slug mode working. Windows
        # PowerShell 5.1 relocates its own cwd for such paths, so only pwsh is
        # exercised here.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "proj[1]"
            root.mkdir()
            result = self.run_init(root, shell=PWSH)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            for name in ("task_plan.md", "findings.md", "progress.md"):
                self.assertTrue((root / name).is_file(), name)

            named = self.run_init(root, "Bracket Plan", shell=PWSH)
            self.assertEqual(0, named.returncode, named.stdout + named.stderr)
            plan_dir = root / ".planning" / f"{date.today().isoformat()}-bracket-plan"
            for name in ("task_plan.md", "findings.md", "progress.md"):
                self.assertTrue((plan_dir / name).is_file(), name)

    def test_slug_init_requires_selector_beside_initializer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scripts = root / "skill" / "scripts"
            scripts.mkdir(parents=True)
            shutil.copy2(INIT_PS1, scripts / "init-session.ps1")
            project = root / "project"
            project.mkdir()

            result = subprocess.run(
                [
                    POWERSHELL,
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(scripts / "init-session.ps1"),
                    "Lonely Plan",
                ],
                cwd=str(project),
                text=True,
                encoding="utf-8-sig",
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertIn("set-active-plan.ps1", flat(result.stderr))
            self.assertFalse((project / ".planning").exists())


if __name__ == "__main__":
    unittest.main()
