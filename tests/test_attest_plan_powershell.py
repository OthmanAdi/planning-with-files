"""Windows containment tests for the PowerShell attestation path."""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ATTEST = REPO_ROOT / "skills" / "planning-with-files" / "scripts" / "attest-plan.ps1"
RESOLVER = REPO_ROOT / "skills" / "planning-with-files" / "scripts" / "resolve-plan-dir.ps1"
INIT_SESSION = REPO_ROOT / "skills" / "planning-with-files" / "scripts" / "init-session.ps1"
SHELL = shutil.which("pwsh") or shutil.which("powershell")
WINDOWS_POWERSHELL = shutil.which("powershell")


class PowerShellAttestationStaticSecurityTests(unittest.TestCase):
    def test_unix_fallback_is_explicitly_fail_closed(self) -> None:
        source = ATTEST.read_text(encoding="utf-8")
        refusal = (
            "Safe no-follow descriptor operations are unavailable in this "
            "PowerShell script on Unix. Use scripts/attest-plan.sh instead."
        )
        self.assertGreaterEqual(source.count(refusal), 3)
        self.assertLess(
            source.index("if (-not $script:IsWindowsHost)"),
            source.index('if ($script:IsWindowsHost -and'),
        )
        self.assertNotIn("[IO.File]::Open($item.FullName", source)
        self.assertNotIn("[IO.File]::WriteAllBytes($Path", source)
        self.assertNotIn("Remove-Item -LiteralPath $Path -Force", source)

    def test_directory_identity_is_frozen_before_each_target_open(self) -> None:
        source = ATTEST.read_text(encoding="utf-8")
        contracts = (
            ("function Open-SafeReadStream", "::OpenRead($Path"),
            ("function Write-SafeAscii", "::OpenAttestationWrite($Path)"),
            ("function Remove-SafeFile", "::OpenDelete($Path)"),
        )
        for function_name, target_open in contracts:
            with self.subTest(function=function_name):
                start = source.index(function_name)
                end = source.find("\nfunction ", start + len(function_name))
                body = source[start : end if end != -1 else len(source)]
                self.assertLess(
                    body.index("Open-TrustedDirectory"), body.index(target_open)
                )
                self.assertIn("-ExpectedDirectoryFinal $directory.FinalPath", body)
                self.assertIn(
                    "-ExpectedDirectoryIdentity $directory.Identity", body
                )

    def test_resolution_failures_have_specific_command_boundary_messages(self) -> None:
        source = ATTEST.read_text(encoding="utf-8")
        self.assertIn("[string] $Target", source)
        for expected in (
            "Multiple plans are available. Set PLAN_ID=<slug>",
            "PLAN_ID=$(Format-Selector $env:PLAN_ID) names no plan directory",
            "PWF_PLAN_ROOT=$(Format-Selector $env:PWF_PLAN_ROOT) did not resolve",
            "-Target $(Format-Selector $Target) did not resolve",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, source)

    def test_resolution_failures_use_single_line_stderr_and_fail_closed(self) -> None:
        source = ATTEST.read_text(encoding="utf-8")
        self.assertNotIn('Write-Error "[plan-attest]', source)
        self.assertIn('[Console]::Error.WriteLine(', source)
        self.assertIn('$script:PlanResolutionFailure = "ResolvedPlan"', source)

    def test_missing_frozen_security_root_fails_closed_before_matching(self) -> None:
        source = ATTEST.read_text(encoding="utf-8")
        start = source.index("function Test-FinalPathWithinSecurityRoot")
        end = source.index("\nfunction Open-TrustedDirectory", start)
        body = source[start:end]
        guard = "if (-not $script:SecurityRootFinalPath) { return $false }"
        self.assertIn(guard, body)
        self.assertLess(body.index(guard), body.index("$candidate ="))

    def test_root_target_comparisons_are_case_sensitive(self) -> None:
        source = ATTEST.read_text(encoding="utf-8")
        self.assertEqual(2, source.count('$Target -ceq "root"'))
        self.assertNotIn('$Target -eq "root"', source)


@unittest.skipUnless(SHELL and os.name != "nt", "Unix PowerShell is unavailable")
class UnixPowerShellAttestationFailClosedTests(unittest.TestCase):
    def test_attestation_refuses_without_no_follow_descriptor_support(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan_dir = root / ".planning" / "safe-plan"
            plan_dir.mkdir(parents=True)
            (plan_dir / "task_plan.md").write_text("# Safe\n", encoding="utf-8")
            env = os.environ.copy()
            env["PLAN_ID"] = "safe-plan"
            env.pop("PWF_PLAN_ROOT", None)

            result = subprocess.run(
                [SHELL, "-NoProfile", "-File", str(ATTEST)],
                cwd=root,
                env=env,
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=False,
                timeout=30,
            )

            self.assertNotEqual(0, result.returncode)
            self.assertIn("Use scripts/attest-plan.sh instead", result.stderr)
            self.assertFalse((plan_dir / ".attestation").exists())


@unittest.skipUnless(SHELL and os.name == "nt", "Windows PowerShell is unavailable")
class PowerShellAttestationContainmentTests(unittest.TestCase):
    host = SHELL

    def _run(
        self,
        root: Path,
        env_extra: dict[str, str] | None = None,
        *script_args: str,
        script: Path = ATTEST,
    ):
        env = os.environ.copy()
        for key in ("PLAN_ID", "PWF_PLAN_ROOT"):
            env.pop(key, None)
        if env_extra:
            env.update(env_extra)
        return subprocess.run(
            [
                self.host,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script),
                *script_args,
            ],
            cwd=root,
            env=env,
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
            timeout=30,
        )

    def _make_link(self, item_type: str, link: Path, target: Path) -> bool:
        command = (
            "& { param($link, $target, $kind) "
            "New-Item -ItemType $kind -Path $link -Target $target "
            "-ErrorAction Stop | Out-Null }"
        )
        created = subprocess.run(
            [
                SHELL,
                "-NoProfile",
                "-Command",
                command,
                str(link),
                str(target),
                item_type,
            ],
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
        )
        if created.returncode != 0 or not link.exists():
            return False
        item = subprocess.run(
            [
                SHELL,
                "-NoProfile",
                "-Command",
                "& { param($path) "
                "if (((Get-Item -LiteralPath $path -Force).Attributes "
                "-band [IO.FileAttributes]::ReparsePoint) -ne 0) { exit 0 } "
                "else { exit 1 } }",
                str(link),
            ],
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
        )
        return item.returncode == 0

    def _make_hardlink(self, link: Path, target: Path) -> bool:
        command = (
            "& { param($link, $target) "
            "New-Item -ItemType HardLink -Path $link -Target $target "
            "-ErrorAction Stop | Out-Null }"
        )
        created = subprocess.run(
            [SHELL, "-NoProfile", "-Command", command, str(link), str(target)],
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
        )
        return created.returncode == 0 and link.exists()

    def test_valid_scoped_plan_is_attested(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan_dir = root / ".planning" / "safe-plan"
            plan_dir.mkdir(parents=True)
            (plan_dir / "task_plan.md").write_text("# Safe\n", encoding="utf-8")
            result = self._run(root, {"PLAN_ID": "safe-plan"})
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue((plan_dir / ".attestation").is_file())

            shown = self._run(root, {"PLAN_ID": "safe-plan"}, "-Show")
            self.assertEqual(0, shown.returncode, shown.stderr)
            self.assertIn("SHA-256:", shown.stdout)

            cleared = self._run(root, {"PLAN_ID": "safe-plan"}, "-Clear")
            self.assertEqual(0, cleared.returncode, cleared.stderr)
            self.assertFalse((plan_dir / ".attestation").exists())

    def test_ambiguous_plans_report_one_actionable_refusal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("alpha", "beta"):
                plan_dir = root / ".planning" / name
                plan_dir.mkdir(parents=True)
                (plan_dir / "task_plan.md").write_text(name, encoding="utf-8")

            result = self._run(root, None, "-Show")

            self.assertEqual(1, result.returncode, result.stderr)
            refusal = "Multiple plans are available. Set PLAN_ID=<slug>"
            self.assertEqual(1, result.stderr.count(refusal), result.stderr)
            self.assertNotIn("No task_plan.md found", result.stderr)
            self.assertFalse(any(root.rglob(".attestation")))
            self.assertFalse((root / ".plan-attestation").exists())

    def test_unreadable_selected_plan_does_not_attest_legacy_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            selected = root / ".planning" / "selected"
            selected.mkdir(parents=True)
            selected_plan = selected / "task_plan.md"
            selected_plan.write_text("selected", encoding="utf-8")
            (root / "task_plan.md").write_text("legacy decoy", encoding="utf-8")

            locker = subprocess.Popen(
                [
                    SHELL,
                    "-NoProfile",
                    "-Command",
                    (
                        "& { param($path) $stream = [IO.File]::Open($path, "
                        "[IO.FileMode]::Open, [IO.FileAccess]::Read, "
                        "[IO.FileShare]::None); try { 'READY'; "
                        "[Console]::In.ReadLine() | Out-Null } finally { "
                        "$stream.Dispose() } }"
                    ),
                    str(selected_plan),
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
            )
            try:
                self.assertEqual("READY", locker.stdout.readline().strip())
                result = self._run(root)
            finally:
                locker.communicate("\n", timeout=30)

            self.assertEqual(1, result.returncode, result.stderr)
            self.assertIn("selected plan could not be read safely", result.stderr)
            self.assertFalse((selected / ".attestation").exists())
            self.assertFalse((root / ".plan-attestation").exists())

    def test_rejected_selectors_name_the_refused_binding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            active = root / ".planning" / "active"
            active.mkdir(parents=True)
            (active / "task_plan.md").write_text("active decoy", encoding="utf-8")
            (root / "task_plan.md").write_text("root decoy", encoding="utf-8")
            missing_root = root / "missing-project"
            missing_root.mkdir()
            cases = (
                ({"PLAN_ID": "missing"}, (), "PLAN_ID=missing"),
                (
                    {"PWF_PLAN_ROOT": str(missing_root)},
                    (),
                    f"PWF_PLAN_ROOT={missing_root}",
                ),
                (
                    {"PWF_PLAN_ROOT": str(missing_root), "PLAN_ID": "missing"},
                    (),
                    "PLAN_ID=missing",
                ),
                (None, ("-Target", "missing"), "-Target missing"),
            )

            for env, args, refusal in cases:
                with self.subTest(refusal=refusal):
                    result = self._run(root, env, *args)
                    self.assertEqual(1, result.returncode, result.stderr)
                    self.assertEqual(1, result.stderr.count(refusal), result.stderr)
                    self.assertNotIn("No task_plan.md found", result.stderr)
                    self.assertFalse((active / ".attestation").exists())
                    self.assertFalse((root / ".plan-attestation").exists())
                    self.assertFalse((missing_root / ".plan-attestation").exists())

    def test_nested_call_returns_the_refusal_to_the_calling_script(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for slug in ("alpha", "beta"):
                plan_dir = root / ".planning" / slug
                plan_dir.mkdir(parents=True)
                (plan_dir / "task_plan.md").write_text(slug, encoding="utf-8")

            result = self._run(root, None, "-Autonomous", script=INIT_SESSION)

            self.assertIn(
                "NOT attested: [plan-attest] Multiple plans are available",
                result.stdout,
                result.stdout + result.stderr,
            )
            self.assertNotIn("[plan-attest]", result.stderr)

    def test_selected_directory_without_a_plan_names_the_cause(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".planning" / "alpha").mkdir(parents=True)

            pinned = self._run(root, {"PLAN_ID": "alpha"})
            self.assertEqual(1, pinned.returncode, pinned.stderr)
            self.assertIn("PLAN_ID=alpha names no plan directory", pinned.stderr)
            self.assertNotIn("could not be read safely", pinned.stderr)

            (root / ".planning" / ".active_plan").write_text("alpha\n", encoding="utf-8")
            active = self._run(root)
            self.assertEqual(1, active.returncode, active.stderr)
            self.assertIn("No task_plan.md found", active.stderr)
            self.assertNotIn("could not be read safely", active.stderr)

    def test_echoed_selectors_cannot_forge_output(self) -> None:
        forged = "x\n[plan-attest] Locked task_plan.md\x1b[2K"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".planning").mkdir()
            cases = (
                ({"PLAN_ID": forged}, ()),
                ({"PWF_PLAN_ROOT": forged}, ()),
                (None, ("-Target", forged)),
            )
            for env, args in cases:
                with self.subTest(env=env, args=args):
                    result = self._run(root, env, *args)
                    self.assertEqual(1, result.returncode, result.stderr)
                    self.assertEqual(1, len(result.stderr.strip().splitlines()), result.stderr)
                    self.assertNotIn("\x1b", result.stderr)

    def test_unaccepted_pin_shapes_report_the_binding_refusal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "task_plan.md").write_text("root decoy", encoding="utf-8")
            for pin in ("relative", "C:relative", r"\\server\share"):
                with self.subTest(pin=pin):
                    result = self._run(root, {"PWF_PLAN_ROOT": pin})
                    self.assertEqual(1, result.returncode, result.stderr)
                    self.assertEqual(1, len(result.stderr.strip().splitlines()), result.stderr)
                    self.assertIn(f"PWF_PLAN_ROOT={pin} must be an absolute local path", result.stderr)
                    self.assertFalse((root / ".plan-attestation").exists())

    def test_root_target_on_a_missing_drive_reports_the_binding_refusal(self) -> None:
        letters = [c for c in "QXYZWV" if not os.path.exists(f"{c}:\\")]
        if not letters:
            self.skipTest("no unused drive letter on this host")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self._run(
                root, {"PWF_PLAN_ROOT": f"{letters[0]}:\\nope"}, "-Target", "root"
            )
            self.assertEqual(1, result.returncode, result.stderr)
            self.assertEqual(1, len(result.stderr.strip().splitlines()), result.stderr)
            self.assertIn("-Target root did not resolve", result.stderr)

    def test_root_target_from_a_plan_directory_writes_the_root_filename(self) -> None:
        """Hooks running from this directory read .plan-attestation, so it stays allowed."""
        with tempfile.TemporaryDirectory() as tmp:
            plan_dir = Path(tmp) / ".planning" / "alpha"
            plan_dir.mkdir(parents=True)
            (plan_dir / "task_plan.md").write_text("alpha", encoding="utf-8")

            result = self._run(plan_dir, None, "-Target", "root")

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue((plan_dir / ".plan-attestation").is_file())

    def test_refusal_is_visible_when_the_caller_captures_only_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            wrapper = root / "wrapper.ps1"
            wrapper.write_text(
                f"$captured = & '{ATTEST}' -Target nope\nexit $LASTEXITCODE\n",
                encoding="utf-8",
            )

            result = self._run(root, None, script=wrapper)

            self.assertEqual(1, result.returncode, result.stderr)
            self.assertIn("-Target nope did not resolve", " ".join(result.stderr.split()))

    def test_target_traversal_and_alias_spellings_are_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan_dir = root / ".planning" / "alpha"
            plan_dir.mkdir(parents=True)
            (plan_dir / "task_plan.md").write_text("alpha", encoding="utf-8")
            for target in ("..\\alpha", "../alpha", ".planning/alpha", "alpha.", "alpha\n"):
                with self.subTest(target=target):
                    result = self._run(root, None, "-Target", target)
                    self.assertEqual(1, result.returncode, result.stderr)
                    self.assertEqual(1, len(result.stderr.strip().splitlines()), result.stderr)
                    self.assertIn("did not resolve to a plan", result.stderr)
                    self.assertFalse((plan_dir / ".attestation").exists())

    def test_target_root_with_pinned_root_writes_plan_attestation(self) -> None:
        """From another cwd, -Target root + PWF_PLAN_ROOT must write .plan-attestation."""
        with tempfile.TemporaryDirectory() as tmp:
            outer = Path(tmp)
            pinned = outer / "pinned"
            pinned.mkdir()
            plan = pinned / "task_plan.md"
            plan.write_text("# Root plan\n", encoding="utf-8")
            cwd = outer / "other"
            cwd.mkdir()

            result = self._run(
                cwd,
                {"PWF_PLAN_ROOT": str(pinned)},
                "-Target",
                "root",
            )

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue((pinned / ".plan-attestation").is_file())
            self.assertFalse((pinned / ".attestation").exists())
            self.assertFalse((cwd / ".plan-attestation").exists())
            self.assertFalse((cwd / ".attestation").exists())

    def test_slug_cwd_invocation_keeps_slug_attestation_name(self) -> None:
        """Attesting while cwd is the slug plan dir still uses .attestation."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan_dir = root / ".planning" / "safe-plan"
            plan_dir.mkdir(parents=True)
            (plan_dir / "task_plan.md").write_text("# Slug\n", encoding="utf-8")
            (root / ".planning" / ".active_plan").write_text(
                "safe-plan\n", encoding="utf-8"
            )

            result = self._run(plan_dir)

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue((plan_dir / ".attestation").is_file())
            self.assertFalse((plan_dir / ".plan-attestation").exists())
            self.assertFalse((root / ".plan-attestation").exists())

    def test_target_junction_escape_is_refused_when_supported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside_tmp:
            root = Path(tmp)
            outside = Path(outside_tmp)
            (root / ".planning").mkdir()
            (outside / "task_plan.md").write_text("# Outside\n", encoding="utf-8")
            junction = root / ".planning" / "escape"
            if not self._make_link("Junction", junction, outside):
                self.skipTest("junction creation is unavailable on this host")
            result = self._run(root, None, "-Target", "escape")
            self.assertEqual(1, result.returncode, result.stderr)
            self.assertFalse((outside / ".attestation").exists())

    def test_nonexistent_pwf_plan_root_reports_binding_refusal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            missing_root = root / "missing-project"
            (root / "task_plan.md").write_text("root decoy", encoding="utf-8")

            result = self._run(root, {"PWF_PLAN_ROOT": str(missing_root)})

            self.assertEqual(1, result.returncode, result.stderr)
            refusal = f"PWF_PLAN_ROOT={missing_root} did not resolve"
            self.assertEqual(1, result.stderr.count(refusal), result.stderr)
            self.assertFalse((root / ".plan-attestation").exists())

    def test_target_root_and_named_plan_attest_exact_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root_plan = root / "task_plan.md"
            root_plan.write_text("root plan", encoding="utf-8")
            selected = root / ".planning" / "selected"
            active = root / ".planning" / "active"
            selected.mkdir(parents=True)
            active.mkdir(parents=True)
            (selected / "task_plan.md").write_text("selected plan", encoding="utf-8")
            (active / "task_plan.md").write_text("active decoy", encoding="utf-8")

            root_result = self._run(root, {"PLAN_ID": "active"}, "-Target", "root")
            named_result = self._run(root, {"PLAN_ID": "active"}, "-Target", "selected")

            self.assertEqual(0, root_result.returncode, root_result.stderr)
            self.assertEqual(0, named_result.returncode, named_result.stderr)
            self.assertTrue((root / ".plan-attestation").is_file())
            self.assertTrue((selected / ".attestation").is_file())
            self.assertFalse((active / ".attestation").exists())

    def test_root_target_keyword_is_case_sensitive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "task_plan.md").write_text("root plan", encoding="utf-8")
            named = root / ".planning" / "Root"
            named.mkdir(parents=True)
            (named / "task_plan.md").write_text("named plan", encoding="utf-8")

            result = self._run(root, None, "-Target", "Root")

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue((named / ".attestation").is_file())
            self.assertFalse((named / ".plan-attestation").exists())
            self.assertFalse((root / ".plan-attestation").exists())

    def test_attest_from_inside_plan_dir_uses_slug_attestation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan_dir = root / ".planning" / "safe-plan"
            plan_dir.mkdir(parents=True)
            plan = plan_dir / "task_plan.md"
            plan.write_text("# First\n", encoding="utf-8")
            (root / ".planning" / ".active_plan").write_text(
                "safe-plan\n", encoding="utf-8"
            )

            initial = self._run(root)
            self.assertEqual(0, initial.returncode, initial.stderr)
            attestation = plan_dir / ".attestation"
            initial_hash = attestation.read_text(encoding="ascii").strip()

            plan.write_text("# Second\n", encoding="utf-8")
            nested = self._run(plan_dir)

            self.assertEqual(0, nested.returncode, nested.stderr)
            self.assertNotEqual(
                initial_hash, attestation.read_text(encoding="ascii").strip()
            )
            self.assertFalse((plan_dir / ".plan-attestation").exists())

            shown = self._run(plan_dir, None, "-Show")
            self.assertEqual(0, shown.returncode, shown.stderr)
            self.assertIn("SHA-256:", shown.stdout)

            cleared = self._run(plan_dir, None, "-Clear")
            self.assertEqual(0, cleared.returncode, cleared.stderr)
            self.assertFalse(attestation.exists())

    def test_traversal_plan_id_cannot_attest_legacy_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "task_plan.md").write_text("# Legacy decoy\n", encoding="utf-8")
            result = self._run(root, {"PLAN_ID": "..\\outside"})
            self.assertNotEqual(0, result.returncode)
            self.assertFalse((root / ".plan-attestation").exists())

    def test_malformed_active_pointer_cannot_attest_legacy_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            planning = root / ".planning"
            planning.mkdir()
            (planning / ".active_plan").write_text("../../outside\n", encoding="utf-8")
            (root / "task_plan.md").write_text("# Legacy decoy\n", encoding="utf-8")
            result = self._run(root)
            self.assertNotEqual(0, result.returncode)
            self.assertFalse((root / ".plan-attestation").exists())

    def test_drive_relative_and_unc_pins_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "task_plan.md").write_text("# Legacy decoy\n", encoding="utf-8")
            for pin in ("C:relative", r"\\server\share"):
                with self.subTest(pin=pin):
                    result = self._run(root, {"PWF_PLAN_ROOT": pin})
                    self.assertNotEqual(0, result.returncode)
                    self.assertFalse((root / ".plan-attestation").exists())

    def test_junction_escape_is_rejected_when_supported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside_tmp:
            root = Path(tmp)
            outside = Path(outside_tmp)
            (root / ".planning").mkdir()
            (outside / "task_plan.md").write_text("# Outside\n", encoding="utf-8")
            junction = root / ".planning" / "escape"
            if not self._make_link("Junction", junction, outside):
                self.skipTest("junction creation is unavailable on this host")
            result = self._run(root, {"PLAN_ID": "escape"})
            self.assertNotEqual(0, result.returncode)
            self.assertFalse((outside / ".attestation").exists())

    def test_stale_resolver_junction_swap_refuses_attest_show_and_clear(self) -> None:
        """A resolver result must not become trusted after its directory swaps.

        The local resolver stub models a valid selection returned just before
        an attacker replaces that path with an external junction. The
        attestation script must independently bind the selected directory to
        the root handle frozen before resolution.
        """
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside_tmp:
            root = Path(tmp)
            planning = root / ".planning"
            planning.mkdir()
            outside = Path(outside_tmp)
            (outside / "task_plan.md").write_text("# Outside\n", encoding="utf-8")
            external_marker = outside / ".attestation"
            external_marker.write_text("EXTERNAL-MARKER", encoding="utf-8")
            junction = planning / "safe-plan"
            if not self._make_link("Junction", junction, outside):
                self.skipTest("junction creation is unavailable on this host")

            script_dir = root / "script-copy"
            script_dir.mkdir()
            copied_attest = script_dir / "attest-plan.ps1"
            shutil.copy2(ATTEST, copied_attest)
            (script_dir / "resolve-plan-dir.ps1").write_text(
                "Write-Output (Join-Path (Get-Location) '.planning\\safe-plan')\n",
                encoding="utf-8",
            )

            for args in ((), ("-Show",), ("-Clear",)):
                with self.subTest(args=args):
                    result = self._run(
                        root,
                        {"PLAN_ID": "safe-plan"},
                        *args,
                        script=copied_attest,
                    )
                    self.assertNotEqual(0, result.returncode)
                    self.assertEqual(
                        "EXTERNAL-MARKER",
                        external_marker.read_text(encoding="utf-8"),
                    )

    def test_symlink_plan_file_is_rejected_when_supported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside_tmp:
            root = Path(tmp)
            outside = Path(outside_tmp) / "task_plan.md"
            outside.write_text("# Outside\n", encoding="utf-8")
            link = root / "task_plan.md"
            if not self._make_link("SymbolicLink", link, outside):
                self.skipTest("file symlink creation is unavailable on this host")
            result = self._run(root)
            self.assertNotEqual(0, result.returncode)
            self.assertFalse((root / ".plan-attestation").exists())

    def test_precreated_attestation_directory_is_never_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan_dir = root / ".planning" / "safe-plan"
            plan_dir.mkdir(parents=True)
            (plan_dir / "task_plan.md").write_text("# Safe\n", encoding="utf-8")
            marker = plan_dir / ".attestation"
            marker.mkdir()
            sentinel = marker / "keep.txt"
            sentinel.write_text("KEEP", encoding="utf-8")

            result = self._run(root, {"PLAN_ID": "safe-plan"})

            self.assertNotEqual(0, result.returncode)
            self.assertTrue(marker.is_dir())
            self.assertEqual("KEEP", sentinel.read_text(encoding="utf-8"))

    def test_precreated_attestation_symlink_is_safe_for_attest_show_and_clear(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside_tmp:
            root = Path(tmp)
            plan_dir = root / ".planning" / "safe-plan"
            plan_dir.mkdir(parents=True)
            (plan_dir / "task_plan.md").write_text("# Safe\n", encoding="utf-8")
            outside = Path(outside_tmp) / "external.txt"
            outside.write_text("EXTERNAL-SENTINEL", encoding="utf-8")
            marker = plan_dir / ".attestation"
            if not self._make_link("SymbolicLink", marker, outside):
                self.skipTest("file symlink creation is unavailable on this host")

            for args in ((), ("-Show",), ("-Clear",)):
                with self.subTest(args=args):
                    result = self._run(root, {"PLAN_ID": "safe-plan"}, *args)
                    self.assertNotEqual(0, result.returncode)
                    self.assertEqual(
                        "EXTERNAL-SENTINEL", outside.read_text(encoding="utf-8")
                    )
                    self.assertTrue(marker.exists())

    def test_precreated_attestation_junction_is_never_followed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside_tmp:
            root = Path(tmp)
            plan_dir = root / ".planning" / "safe-plan"
            plan_dir.mkdir(parents=True)
            (plan_dir / "task_plan.md").write_text("# Safe\n", encoding="utf-8")
            outside = Path(outside_tmp)
            sentinel = outside / "keep.txt"
            sentinel.write_text("KEEP", encoding="utf-8")
            marker = plan_dir / ".attestation"
            if not self._make_link("Junction", marker, outside):
                self.skipTest("junction creation is unavailable on this host")

            result = self._run(root, {"PLAN_ID": "safe-plan"})

            self.assertNotEqual(0, result.returncode)
            self.assertEqual("KEEP", sentinel.read_text(encoding="utf-8"))

    def test_precreated_attestation_hardlink_is_safe_for_attest_show_and_clear(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan_dir = root / ".planning" / "safe-plan"
            plan_dir.mkdir(parents=True)
            (plan_dir / "task_plan.md").write_text("# Safe\n", encoding="utf-8")
            outside = root / "external.txt"
            outside.write_text("EXTERNAL-HARDLINK-SENTINEL", encoding="utf-8")
            marker = plan_dir / ".attestation"
            if not self._make_hardlink(marker, outside):
                self.skipTest("hardlink creation is unavailable on this host")

            for args in ((), ("-Show",), ("-Clear",)):
                with self.subTest(args=args):
                    result = self._run(root, {"PLAN_ID": "safe-plan"}, *args)
                    self.assertNotEqual(0, result.returncode)
                    self.assertNotIn(
                        "EXTERNAL-HARDLINK-SENTINEL",
                        result.stdout + result.stderr,
                    )
                    self.assertEqual(
                        "EXTERNAL-HARDLINK-SENTINEL",
                        outside.read_text(encoding="utf-8"),
                    )
                    self.assertTrue(marker.exists())

    def test_show_rejects_linked_nonce_without_leaking_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside_tmp:
            root = Path(tmp)
            plan_dir = root / ".planning" / "safe-plan"
            plan_dir.mkdir(parents=True)
            (plan_dir / "task_plan.md").write_text("# Safe\n", encoding="utf-8")
            initial = self._run(root, {"PLAN_ID": "safe-plan"})
            self.assertEqual(0, initial.returncode, initial.stderr)
            secret = Path(outside_tmp) / "secret.txt"
            secret.write_text("DO-NOT-LEAK-THIS", encoding="utf-8")
            nonce = plan_dir / ".nonce"
            if not self._make_link("SymbolicLink", nonce, secret):
                self.skipTest("file symlink creation is unavailable on this host")

            result = self._run(root, {"PLAN_ID": "safe-plan"}, "-Show")

            self.assertNotEqual(0, result.returncode)
            self.assertNotIn("DO-NOT-LEAK-THIS", result.stdout + result.stderr)

    def test_active_pointer_symlink_is_not_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside_tmp:
            root = Path(tmp)
            planning = root / ".planning"
            plan_dir = planning / "safe-plan"
            plan_dir.mkdir(parents=True)
            (plan_dir / "task_plan.md").write_text("# Safe\n", encoding="utf-8")
            external_pointer = Path(outside_tmp) / "pointer.txt"
            external_pointer.write_text("safe-plan\n", encoding="utf-8")
            if not self._make_link(
                "SymbolicLink", planning / ".active_plan", external_pointer
            ):
                self.skipTest("file symlink creation is unavailable on this host")

            resolved = self._run(root, script=RESOLVER)
            result = self._run(root)

            self.assertEqual(0, resolved.returncode, resolved.stderr)
            self.assertEqual("", resolved.stdout.strip())
            self.assertNotEqual(0, result.returncode)
            self.assertFalse((plan_dir / ".attestation").exists())

    def test_dangling_active_pointer_cannot_attest_legacy_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside_tmp:
            root = Path(tmp)
            planning = root / ".planning"
            planning.mkdir()
            (root / "task_plan.md").write_text("# Legacy decoy\n", encoding="utf-8")
            external_pointer = Path(outside_tmp) / "pointer.txt"
            external_pointer.write_text("safe-plan\n", encoding="utf-8")
            active_pointer = planning / ".active_plan"
            if not self._make_link("SymbolicLink", active_pointer, external_pointer):
                self.skipTest("file symlink creation is unavailable on this host")
            external_pointer.unlink()

            resolved = self._run(root, script=RESOLVER)
            result = self._run(root)

            self.assertEqual(0, resolved.returncode, resolved.stderr)
            self.assertEqual("", resolved.stdout.strip())
            self.assertNotEqual(0, result.returncode)
            self.assertFalse((root / ".plan-attestation").exists())


@unittest.skipUnless(
    os.name == "nt" and SHELL and WINDOWS_POWERSHELL and SHELL != WINDOWS_POWERSHELL,
    "Windows PowerShell 5.1 is already the default host or is unavailable",
)
class WindowsPowerShell51AttestationTests(PowerShellAttestationContainmentTests):
    """pwsh is preferred above, so run the same contract on the 5.1 host users have."""

    host = WINDOWS_POWERSHELL


if __name__ == "__main__":
    unittest.main()
