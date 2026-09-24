"""Named-plan coverage for Cursor's native PowerShell hook route.

The contract runs under Windows PowerShell 5.1 (what hooks.windows.json
launches) and, when installed, under pwsh 7 as well: the two disagree on
details such as $? after a subexpression, and a guard that is dead on one of
them is invisible when only the other runs.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CURSOR_HOOKS = REPO_ROOT / ".cursor" / "hooks"
WINDOWS_POWERSHELL = shutil.which("powershell.exe") or shutil.which("powershell")
PWSH = shutil.which("pwsh")
POWERSHELL = WINDOWS_POWERSHELL or PWSH
SCRUB_VARS = ("PLAN_ID", "PWF_PLAN_ROOT", "PLANNING_DISABLED")


@unittest.skipUnless(POWERSHELL, "requires PowerShell")
class CursorPowerShellNamedPlanTests(unittest.TestCase):
    interpreter = POWERSHELL

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="pwf-cursor-ps-named-")
        self.workspace = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def clean_env(self, **extra: str) -> dict[str, str]:
        env = os.environ.copy()
        for name in SCRUB_VARS:
            env.pop(name, None)
        env.update(extra)
        return env

    def write_root_plan(self, marker: str = "ROOT-PLAN-MARKER") -> None:
        (self.workspace / "task_plan.md").write_text(
            f"# {marker}\n### Phase 1\n**Status:** pending\n",
            encoding="utf-8",
        )
        (self.workspace / "progress.md").write_text(
            "ROOT-PROGRESS-MARKER\n", encoding="utf-8"
        )

    def write_named_plan(
        self,
        slug: str,
        marker: str,
        *,
        active: bool = False,
    ) -> Path:
        plan_dir = self.workspace / ".planning" / slug
        plan_dir.mkdir(parents=True)
        (plan_dir / "task_plan.md").write_text(
            f"# {marker}\n### Phase 1\n**Status:** pending\n",
            encoding="utf-8",
        )
        (plan_dir / "progress.md").write_text(
            f"{marker}-PROGRESS\n", encoding="utf-8"
        )
        if active:
            (self.workspace / ".planning" / ".active_plan").write_text(
                f"{slug}\n", encoding="utf-8"
            )
        return plan_dir

    def run_hook(
        self,
        name: str,
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        hooks_dir: Path | None = None,
        constrained: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        assert self.interpreter is not None
        script = (hooks_dir or CURSOR_HOOKS) / f"{name}.ps1"
        if constrained:
            # WDAC / AppLocker machines run every script in ConstrainedLanguage;
            # setting the mode in-process reproduces that for the hook.
            launch = [
                "-Command",
                "$ExecutionContext.SessionState.LanguageMode = 'ConstrainedLanguage'; "
                f"& '{script}'; exit $LASTEXITCODE",
            ]
        else:
            launch = ["-File", str(script)]
        return subprocess.run(
            [
                self.interpreter,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                *launch,
            ],
            cwd=str(cwd or self.workspace),
            env=env or self.clean_env(),
            text=True,
            encoding="utf-8-sig",
            capture_output=True,
            check=False,
            timeout=120,
        )

    def run_all_hooks(
        self, env: dict[str, str] | None = None
    ) -> dict[str, subprocess.CompletedProcess[str]]:
        return {
            name: self.run_hook(name, env=env)
            for name in (
                "session-start",
                "pre-tool-use",
                "post-tool-use",
                "stop",
                "user-prompt-submit",
            )
        }

    def test_active_named_plan_reaches_all_native_hooks(self) -> None:
        marker = "NAMED-PLAN-MARKER"
        self.write_named_plan("plan-a", marker, active=True)

        results = self.run_all_hooks()

        for result in results.values():
            self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn(
            marker,
            json.loads(results["session-start"].stdout)["additional_context"],
        )
        self.assertEqual(
            {"permission": "allow"},
            json.loads(results["pre-tool-use"].stdout),
        )
        self.assertIn(
            "Update progress.md",
            json.loads(results["post-tool-use"].stdout)["additional_context"],
        )
        self.assertIn(
            "Task incomplete (0/1 phases done)", results["stop"].stdout
        )
        self.assertIn(marker, results["user-prompt-submit"].stdout)
        self.assertIn(
            f"{marker}-PROGRESS", results["user-prompt-submit"].stdout
        )

    def test_legacy_root_still_reaches_all_native_hooks(self) -> None:
        self.write_root_plan()

        results = self.run_all_hooks()

        for result in results.values():
            self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn(
            "ROOT-PLAN-MARKER",
            json.loads(results["session-start"].stdout)["additional_context"],
        )
        self.assertEqual(
            {"permission": "allow"},
            json.loads(results["pre-tool-use"].stdout),
        )
        self.assertIn(
            "Update progress.md",
            json.loads(results["post-tool-use"].stdout)["additional_context"],
        )
        self.assertIn(
            "Task incomplete (0/1 phases done)", results["stop"].stdout
        )
        self.assertIn("ROOT-PLAN-MARKER", results["user-prompt-submit"].stdout)

    def test_plan_id_overrides_the_shared_active_pointer(self) -> None:
        self.write_named_plan("plan-a", "ACTIVE-PLAN-MARKER", active=True)
        self.write_named_plan("plan-b", "PINNED-PLAN-MARKER")

        result = self.run_hook(
            "user-prompt-submit",
            env=self.clean_env(PLAN_ID="plan-b"),
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("PINNED-PLAN-MARKER", result.stdout)
        self.assertNotIn("ACTIVE-PLAN-MARKER", result.stdout)

    def test_invalid_plan_id_fails_closed_across_hooks(self) -> None:
        self.write_root_plan()
        self.write_named_plan("plan-a", "ACTIVE-PLAN-MARKER", active=True)
        env = self.clean_env(PLAN_ID="missing-plan")

        results = self.run_all_hooks(env)

        for result in results.values():
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertNotIn("ROOT-PLAN-MARKER", result.stdout)
            self.assertNotIn("ACTIVE-PLAN-MARKER", result.stdout)
        self.assertIn('"permission":"allow"', results["pre-tool-use"].stdout)
        self.assertEqual("{}", results["post-tool-use"].stdout.strip())
        self.assertEqual("", results["stop"].stdout.strip())
        self.assertIn("PLAN_ID", results["user-prompt-submit"].stdout)
        self.assertIn("nothing injected", results["user-prompt-submit"].stdout)

    def test_multiple_named_plans_require_an_explicit_plan_id(self) -> None:
        self.write_named_plan("plan-a", "PLAN-A-MARKER")
        self.write_named_plan("plan-b", "PLAN-B-MARKER")

        result = self.run_hook("user-prompt-submit")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("Multiple plans are available", result.stdout)
        self.assertNotIn("PLAN-A-MARKER", result.stdout)
        self.assertNotIn("PLAN-B-MARKER", result.stdout)

    def test_plan_root_pin_resolves_a_nested_named_plan(self) -> None:
        parent = self.workspace
        project = parent / "project"
        project.mkdir()
        self.workspace = project
        self.write_named_plan("plan-a", "NESTED-NAMED-MARKER", active=True)
        self.workspace = parent
        self.write_root_plan("PARENT-ROOT-MARKER")

        result = self.run_hook(
            "user-prompt-submit",
            cwd=parent,
            env=self.clean_env(PWF_PLAN_ROOT=str(project)),
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("NESTED-NAMED-MARKER", result.stdout)
        self.assertNotIn("PARENT-ROOT-MARKER", result.stdout)

    def test_stale_pointer_falls_through_to_the_root_plan(self) -> None:
        # inject-plan.sh ignores a pointer that names no plan and injects the
        # legacy root; this route must not refuse what every other route serves.
        self.write_root_plan()
        (self.workspace / ".planning").mkdir()
        (self.workspace / ".planning" / ".active_plan").write_text(
            "gone-plan\n", encoding="utf-8"
        )

        results = self.run_all_hooks()

        for result in results.values():
            self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("ROOT-PLAN-MARKER", results["user-prompt-submit"].stdout)
        self.assertIn("ROOT-PLAN-MARKER", results["pre-tool-use"].stdout)
        self.assertIn("Task incomplete (0/1 phases done)", results["stop"].stdout)

    def test_dot_named_and_invalid_slug_dirs_do_not_block_the_root_plan(self) -> None:
        # The resolver skips both shapes; the selection scan must skip them too,
        # or a root plan next to an archive directory is refused.
        self.write_root_plan()
        for name in (".archived", "Mein Plan"):
            plan_dir = self.workspace / ".planning" / name
            plan_dir.mkdir(parents=True)
            (plan_dir / "task_plan.md").write_text(
                "# HIDDEN-MARKER\n### Phase 1\n**Status:** pending\n", encoding="utf-8"
            )

        result = self.run_hook("user-prompt-submit")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("ROOT-PLAN-MARKER", result.stdout)
        self.assertNotIn("HIDDEN-MARKER", result.stdout)

    def test_directory_pointer_fails_closed(self) -> None:
        self.write_root_plan()
        (self.workspace / ".planning" / ".active_plan").mkdir(parents=True)

        results = self.run_all_hooks()

        for result in results.values():
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertNotIn("ROOT-PLAN-MARKER", result.stdout)
        self.assertIn("(unsafe-pointer)", results["user-prompt-submit"].stdout)
        self.assertIn("nothing injected", results["user-prompt-submit"].stdout)
        self.assertIn('"permission":"allow"', results["pre-tool-use"].stdout)

    def test_symlinked_pointer_fails_closed_and_a_plain_pointer_resolves(self) -> None:
        # #275: the pointer check is LinkType (symlink, junction), not the
        # ReparsePoint attribute that every OneDrive Files On-Demand file carries.
        self.write_named_plan("plan-a", "ACTIVE-PLAN-MARKER", active=True)
        pointer = self.workspace / ".planning" / ".active_plan"
        outside = self.workspace / "elsewhere.txt"
        outside.write_text("plan-a\n", encoding="utf-8")
        plain = self.run_hook("user-prompt-submit", env=self.clean_env())
        self.assertEqual(0, plain.returncode, plain.stderr)
        self.assertIn("ACTIVE-PLAN-MARKER", plain.stdout)
        pointer.unlink()
        try:
            pointer.symlink_to(outside)
        except OSError as exc:
            self.skipTest(f"file symlinks are unavailable: {exc}")
        try:
            linked = self.run_hook("user-prompt-submit", env=self.clean_env())
        finally:
            pointer.unlink()
        self.assertEqual(0, linked.returncode, linked.stderr)
        self.assertIn("(unsafe-pointer)", linked.stdout)
        self.assertNotIn("ACTIVE-PLAN-MARKER", linked.stdout)

    def test_invalid_plan_id_notice_names_the_id(self) -> None:
        self.write_named_plan("plan-a", "ACTIVE-PLAN-MARKER", active=True)

        result = self.run_hook(
            "user-prompt-submit", env=self.clean_env(PLAN_ID="missing-plan")
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn(
            "PLAN_ID does not name a plan directory under .planning: missing-plan",
            result.stdout,
        )
        self.assertNotIn("ACTIVE-PLAN-MARKER", result.stdout)

    def test_broken_pin_notice_names_the_pin(self) -> None:
        self.write_root_plan()
        missing = self.workspace / "does-not-exist"

        result = self.run_hook(
            "user-prompt-submit", env=self.clean_env(PWF_PLAN_ROOT=str(missing))
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn(
            f"PWF_PLAN_ROOT is not a supported absolute local directory: {missing}",
            result.stdout,
        )
        self.assertNotIn("ROOT-PLAN-MARKER", result.stdout)

    def test_traversal_pointer_text_falls_through_to_the_root_plan(self) -> None:
        # Parity row 07c: the pointer text is an invalid slug, so every canonical
        # route ignores it and serves the root plan.
        self.write_root_plan()
        (self.workspace / ".planning").mkdir()
        (self.workspace / ".planning" / ".active_plan").write_text(
            "../escape\n", encoding="utf-8"
        )

        result = self.run_hook("user-prompt-submit")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("ROOT-PLAN-MARKER", result.stdout)

    def test_empty_pointer_falls_through_like_every_other_route(self) -> None:
        # Parity rows 27 and 28: Get-Content -Raw yields $null for a zero-byte
        # pointer; the resolver must not raise into the caller.
        self.write_named_plan("plan-a", "PLAN-A-MARKER")
        (self.workspace / ".planning" / ".active_plan").write_bytes(b"")
        named = self.run_hook("user-prompt-submit")
        self.assertEqual(0, named.returncode, named.stderr)
        self.assertIn("PLAN-A-MARKER", named.stdout)

        shutil.rmtree(self.workspace / ".planning" / "plan-a")
        self.write_root_plan()
        root = self.run_hook("user-prompt-submit")
        self.assertEqual(0, root.returncode, root.stderr)
        self.assertIn("ROOT-PLAN-MARKER", root.stdout)

    def test_plan_text_reaches_cursor_as_utf8(self) -> None:
        # The OEM code page turned the em-dash into "-" and non-ASCII plan text
        # into "?" on both interpreters.
        self.write_root_plan("ROOT \u00c4rger \u4e2d\u6587")

        result = self.run_hook("user-prompt-submit")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("ACTIVE PLAN \u2014 current state:", result.stdout)
        self.assertIn("ROOT \u00c4rger \u4e2d\u6587", result.stdout)

    @unittest.skipUnless(os.name == "nt", "junctions are a Windows shape")
    def test_junction_escaping_the_project_is_refused_silently(self) -> None:
        # A valid slug that is a junction to a directory outside the project
        # fails containment. inject-plan.sh injects nothing and says nothing.
        outside = Path(self._tmp.name).parent / f"{Path(self._tmp.name).name}-outside"
        outside.mkdir()
        self.addCleanup(shutil.rmtree, outside, True)
        (outside / "task_plan.md").write_text(
            "# OUTSIDE-MARKER\n### Phase 1\n**Status:** pending\n", encoding="utf-8"
        )
        self.write_root_plan()
        (self.workspace / ".planning").mkdir()
        link = self.workspace / ".planning" / "plan-a"
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(outside)],
            capture_output=True,
            check=True,
        )
        try:
            result = self.run_hook("user-prompt-submit")
        finally:
            # Remove the junction before tearDown removes the tree.
            link.rmdir()

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("", result.stdout.strip())

    def test_legacy_root_survives_constrained_language_mode(self) -> None:
        # [pscustomobject] is rejected under ConstrainedLanguage; the shared
        # context must stay a plain hashtable so the legacy root keeps injecting.
        self.write_root_plan()

        result = self.run_hook("user-prompt-submit", constrained=True)

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("ROOT-PLAN-MARKER", result.stdout)
        self.assertNotIn("could not be resolved", result.stdout)

    def test_pre_tool_use_answers_when_the_helper_is_missing(self) -> None:
        # A user who copied only the hook files, without the shared helper, must
        # still get the protocol response: the hook never blocks a tool.
        hooks_dir = self.workspace / ".cursor" / "hooks"
        hooks_dir.mkdir(parents=True)
        shutil.copy(CURSOR_HOOKS / "pre-tool-use.ps1", hooks_dir / "pre-tool-use.ps1")
        self.write_root_plan()

        result = self.run_hook("pre-tool-use", hooks_dir=hooks_dir)

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn('"permission":"allow"', result.stdout)


@unittest.skipUnless(
    PWSH and WINDOWS_POWERSHELL, "requires both pwsh and Windows PowerShell"
)
class CursorPwshNamedPlanTests(CursorPowerShellNamedPlanTests):
    """The same contract under pwsh 7, when the primary run used 5.1."""

    interpreter = PWSH


if __name__ == "__main__":
    unittest.main()
