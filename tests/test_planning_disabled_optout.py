"""Issue #195: PLANNING_DISABLED=1 per-invocation opt-out.

A one-shot session (codex exec, CI bot, sub-orchestrator) that merely shares a
cwd with an incomplete plan must be able to opt out of every hook: no plan
injection, no stop followup, no plan-file mutation. These tests run the real
hook scripts in a temp dir containing a legacy root task_plan.md (the exact
attachment path the issue reports) with and without the env var.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CODEX_HOOKS = REPO / ".codex" / "hooks"
COPILOT_HOOKS = REPO / ".github" / "hooks" / "scripts"
CURSOR_HOOKS = REPO / ".cursor" / "hooks"
SCRIPTS = REPO / "scripts"
POWERSHELL = (
    shutil.which("pwsh")
    or shutil.which("powershell.exe")
    or shutil.which("powershell")
)

PLAN = "# Test Plan\n### Phase 1: something\n**Status:** in_progress\n"


def run_sh(
    script: Path, cwd: Path, disabled: bool, input_data: str = ""
) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.pop("PLANNING_DISABLED", None)
    if disabled:
        env["PLANNING_DISABLED"] = "1"
    return subprocess.run(
        ["sh", str(script)],
        cwd=str(cwd),
        env=env,
        input=input_data,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )


def run_powershell(
    script: Path, cwd: Path, disabled: bool
) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.pop("PLANNING_DISABLED", None)
    if disabled:
        env["PLANNING_DISABLED"] = "1"
    return subprocess.run(
        [
            str(POWERSHELL),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
        ],
        cwd=str(cwd),
        env=env,
        input='{"error":{"message":"fixture failure"}}',
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )


class PlanningDisabledOptOutTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.cwd = Path(self._tmp.name)
        (self.cwd / "task_plan.md").write_text(PLAN, encoding="utf-8")
        (self.cwd / "progress.md").write_text("progress line\n", encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    # --- Codex hooks (the platform #195 reports against) ---

    def test_codex_user_prompt_submit_stays_silent_when_disabled(self) -> None:
        baseline = run_sh(CODEX_HOOKS / "user-prompt-submit.sh", self.cwd, disabled=False)
        self.assertIn("ACTIVE PLAN", baseline.stdout)
        disabled = run_sh(CODEX_HOOKS / "user-prompt-submit.sh", self.cwd, disabled=True)
        self.assertEqual(disabled.stdout.strip(), "")
        self.assertEqual(disabled.returncode, 0)

    def test_codex_stop_emits_no_followup_when_disabled(self) -> None:
        baseline = run_sh(CODEX_HOOKS / "stop.sh", self.cwd, disabled=False)
        self.assertIn("followup_message", baseline.stdout)
        disabled = run_sh(CODEX_HOOKS / "stop.sh", self.cwd, disabled=True)
        self.assertEqual(disabled.stdout.strip(), "")
        self.assertEqual(disabled.returncode, 0)

    def test_codex_pre_tool_use_still_allows_but_skips_context(self) -> None:
        disabled = run_sh(CODEX_HOOKS / "pre-tool-use.sh", self.cwd, disabled=True)
        self.assertIn('"decision": "allow"', disabled.stdout)
        self.assertEqual(disabled.stderr.strip(), "")

    def test_codex_post_tool_use_stays_silent_when_disabled(self) -> None:
        disabled = run_sh(CODEX_HOOKS / "post-tool-use.sh", self.cwd, disabled=True)
        self.assertEqual(disabled.stdout.strip(), "")

    def test_codex_session_start_stays_silent_when_disabled(self) -> None:
        disabled = run_sh(CODEX_HOOKS / "session-start.sh", self.cwd, disabled=True)
        self.assertEqual(disabled.stdout.strip(), "")

    def test_codex_pre_compact_stays_silent_when_disabled(self) -> None:
        disabled = run_sh(CODEX_HOOKS / "pre-compact.sh", self.cwd, disabled=True)
        self.assertEqual(disabled.stdout.strip(), "")

    def test_codex_adapter_reports_not_attached_when_disabled(self) -> None:
        sys.path.insert(0, str(CODEX_HOOKS))
        try:
            import codex_hook_adapter as adapter
        finally:
            sys.path.pop(0)
        old = os.environ.pop("PLANNING_DISABLED", None)
        try:
            self.assertTrue(adapter.is_session_attached(self.cwd, None))
            os.environ["PLANNING_DISABLED"] = "1"
            self.assertFalse(adapter.is_session_attached(self.cwd, None))
        finally:
            os.environ.pop("PLANNING_DISABLED", None)
            if old is not None:
                os.environ["PLANNING_DISABLED"] = old

    # --- Canonical dispatchers (Claude Code and mirrors) ---

    def test_inject_plan_stays_silent_when_disabled(self) -> None:
        baseline = run_sh(SCRIPTS / "inject-plan.sh", self.cwd, disabled=False)
        self.assertIn("ACTIVE PLAN", baseline.stdout)
        disabled = run_sh(SCRIPTS / "inject-plan.sh", self.cwd, disabled=True)
        self.assertEqual(disabled.stdout.strip(), "")

    def test_gate_stop_stays_silent_when_disabled(self) -> None:
        disabled = run_sh(SCRIPTS / "gate-stop.sh", self.cwd, disabled=True)
        self.assertEqual(disabled.stdout.strip(), "")
        self.assertEqual(disabled.returncode, 0)

    def test_check_complete_stays_silent_when_disabled(self) -> None:
        baseline = run_sh(SCRIPTS / "check-complete.sh", self.cwd, disabled=False)
        self.assertNotEqual(baseline.stdout.strip(), "")
        disabled = run_sh(SCRIPTS / "check-complete.sh", self.cwd, disabled=True)
        self.assertEqual(disabled.stdout.strip(), "")

    # --- Acceptance criterion from #195: plan files byte-for-byte unchanged ---

    def test_plan_files_unchanged_after_disabled_hook_pass(self) -> None:
        for script in [
            CODEX_HOOKS / "session-start.sh",
            CODEX_HOOKS / "user-prompt-submit.sh",
            CODEX_HOOKS / "pre-tool-use.sh",
            CODEX_HOOKS / "post-tool-use.sh",
            CODEX_HOOKS / "stop.sh",
            CODEX_HOOKS / "pre-compact.sh",
            SCRIPTS / "inject-plan.sh",
            SCRIPTS / "gate-stop.sh",
            SCRIPTS / "check-complete.sh",
        ]:
            run_sh(script, self.cwd, disabled=True)
        self.assertEqual((self.cwd / "task_plan.md").read_text(encoding="utf-8"), PLAN)
        self.assertEqual(
            (self.cwd / "progress.md").read_text(encoding="utf-8"), "progress line\n"
        )

    def test_copilot_shell_hooks_skip_context_when_disabled(self) -> None:
        # Each hook is run twice against the same fixture. Asserting only the
        # disabled run would pass against a fleet of hooks that emit {} no
        # matter what, which is the silent-death class this repo has shipped
        # twice, so the enabled run is the anti-vacuity baseline: it has to
        # produce the context that the disabled run must not.
        live = 0
        for name in (
            "session-start.sh",
            "pre-tool-use.sh",
            "post-tool-use.sh",
            "agent-stop.sh",
            "error-occurred.sh",
        ):
            with self.subTest(hook=name):
                enabled = run_sh(
                    COPILOT_HOOKS / name,
                    self.cwd,
                    disabled=False,
                    input_data='{"error":{"message":"fixture failure"}}',
                )
                self.assertEqual(0, enabled.returncode, enabled.stderr)
                enabled_output = json.loads(
                    enabled.stdout.lstrip("\ufeff")
                ).get("hookSpecificOutput", {})
                if "additionalContext" in enabled_output:
                    live += 1

                result = run_sh(
                    COPILOT_HOOKS / name,
                    self.cwd,
                    disabled=True,
                    input_data='{"error":{"message":"fixture failure"}}',
                )
                self.assertEqual(0, result.returncode, result.stderr)
                payload = json.loads(result.stdout.lstrip("\ufeff"))
                # Disabled means no opinion: no context, and for PreToolUse no
                # permission decision either, so Copilot's own flow decides.
                self.assertEqual({}, payload)

        # error-occurred.sh JSON-escapes through python3 and goes quiet where
        # that probe finds nothing, so four is the floor, not five.
        self.assertGreaterEqual(
            live,
            4,
            "no Copilot shell hook produced context with the opt-out unset; "
            "the disabled-run assertions above cannot mean anything",
        )

    # --- Every distributed copy carries the guard ---

    def test_all_check_complete_copies_carry_the_guard(self) -> None:
        copies = list(REPO.glob("**/check-complete.sh")) + list(
            REPO.glob("**/check-complete.ps1")
        )
        self.assertGreater(len(copies), 10)
        for copy in copies:
            if "node_modules" in copy.parts:
                continue
            text = copy.read_text(encoding="utf-8", errors="replace")
            self.assertIn(
                "PLANNING_DISABLED",
                text,
                f"missing opt-out guard: {copy.relative_to(REPO)}",
            )


@unittest.skipUnless(POWERSHELL, "PowerShell is not available")
class CopilotPowerShellPlanningDisabledTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.cwd = Path(self._tmp.name)
        (self.cwd / "task_plan.md").write_text(PLAN, encoding="utf-8")
        (self.cwd / "progress.md").write_text("progress line\n", encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_copilot_powershell_hooks_skip_context_when_disabled(self) -> None:
        # None of the five PowerShell hooks shells out to escape JSON, so every
        # one of them must produce context with the opt-out unset. A hook that
        # goes quiet in both runs is dead, not disabled.
        for name in (
            "session-start.ps1",
            "pre-tool-use.ps1",
            "post-tool-use.ps1",
            "agent-stop.ps1",
            "error-occurred.ps1",
        ):
            with self.subTest(hook=name):
                enabled = run_powershell(
                    COPILOT_HOOKS / name, self.cwd, disabled=False
                )
                self.assertEqual(0, enabled.returncode, enabled.stderr)
                enabled_output = json.loads(
                    enabled.stdout.lstrip("\ufeff")
                ).get("hookSpecificOutput", {})
                self.assertIn(
                    "additionalContext",
                    enabled_output,
                    f"{name} emitted no context with the opt-out unset, so the "
                    "disabled-run assertion below proves nothing",
                )

                result = run_powershell(
                    COPILOT_HOOKS / name, self.cwd, disabled=True
                )
                self.assertEqual(0, result.returncode, result.stderr)
                payload = json.loads(result.stdout.lstrip("\ufeff"))
                # Disabled means no opinion: no context, and for PreToolUse no
                # permission decision either, so Copilot's own flow decides.
                self.assertEqual({}, payload)


CURSOR_HOOK_NAMES = (
    "session-start",
    "pre-tool-use",
    "post-tool-use",
    "stop",
    "user-prompt-submit",
)


class CursorPlanningDisabledTests(unittest.TestCase):
    """Cursor hook opt-out responses stay valid for their event schemas.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.cwd = Path(self._tmp.name)
        (self.cwd / "task_plan.md").write_text(PLAN, encoding="utf-8")
        (self.cwd / "progress.md").write_text("progress line\n", encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _expected_disabled(self, name: str) -> str:
        return {
            "session-start": "{}",
            "pre-tool-use": '{"permission":"allow"}',
            "post-tool-use": "{}",
        }.get(name, "")

    def test_cursor_shell_hooks_go_inert_when_disabled(self) -> None:
        for name in CURSOR_HOOK_NAMES:
            with self.subTest(hook=f"{name}.sh"):
                script = CURSOR_HOOKS / f"{name}.sh"
                enabled = run_sh(script, self.cwd, disabled=False)
                disabled = run_sh(script, self.cwd, disabled=True)
                self.assertEqual(0, enabled.returncode, enabled.stderr)
                self.assertEqual(0, disabled.returncode, disabled.stderr)
                inert = self._expected_disabled(name)
                if name == "pre-tool-use":
                    # Permission hooks must always return an allow response;
                    # the opt-out only affects injected plan context.
                    self.assertEqual(inert, disabled.stdout.strip())
                    self.assertEqual(inert, enabled.stdout.strip())
                    continue
                self.assertNotEqual(
                    inert,
                    (enabled.stdout + enabled.stderr).strip(),
                    f"{name}.sh produced its inert output with the opt-out "
                    "unset, so the disabled assertion below proves nothing",
                )
                self.assertEqual(
                    inert, (disabled.stdout + disabled.stderr).strip()
                )

    @unittest.skipUnless(POWERSHELL, "PowerShell is not available")
    def test_cursor_powershell_hooks_go_inert_when_disabled(self) -> None:
        for name in CURSOR_HOOK_NAMES:
            with self.subTest(hook=f"{name}.ps1"):
                script = CURSOR_HOOKS / f"{name}.ps1"
                enabled = run_powershell(script, self.cwd, disabled=False)
                disabled = run_powershell(script, self.cwd, disabled=True)
                self.assertEqual(0, enabled.returncode, enabled.stderr)
                self.assertEqual(0, disabled.returncode, disabled.stderr)
                inert = self._expected_disabled(name)
                if name == "pre-tool-use":
                    self.assertEqual(inert, disabled.stdout.strip().lstrip("﻿"))
                    self.assertEqual(inert, enabled.stdout.strip().lstrip("﻿"))
                    continue
                self.assertNotEqual(
                    inert,
                    (enabled.stdout + enabled.stderr).strip().lstrip("﻿"),
                    f"{name}.ps1 produced its inert output with the opt-out "
                    "unset, so the disabled assertion below proves nothing",
                )
                self.assertEqual(
                    inert,
                    (disabled.stdout + disabled.stderr).strip().lstrip("﻿"),
                )

    @unittest.skipUnless(POWERSHELL, "PowerShell is not available")
    def test_cursor_stop_ps1_is_silent_on_an_unstructured_plan(self) -> None:
        # issue #191, the copy the fix never reached. stop.sh has carried the
        # zero-phase guard since v3.2.0; stop.ps1 answered "0/0 phases done"
        # and auto-continued on a plan that was never phase-structured.
        (self.cwd / "task_plan.md").write_text(
            "# Notes\n\nThis file has no phase structure.\n", encoding="utf-8"
        )
        result = run_powershell(CURSOR_HOOKS / "stop.ps1", self.cwd, disabled=False)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("", (result.stdout + result.stderr).strip().lstrip("﻿"))


if __name__ == "__main__":
    unittest.main()
