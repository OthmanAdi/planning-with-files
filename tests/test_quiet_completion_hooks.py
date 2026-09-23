"""Completed plans stay quiet in automatic Stop checks, not explicit reports."""
from __future__ import annotations

import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys

import pytest


REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "skills" / "planning-with-files" / "scripts"
CHECKERS = ("sh-checker", "ps-checker")
HOOKS = ("claude-plugin", "standalone-skill", "codex")


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "project with spaces"
    root.mkdir()
    env = {
        key: value for key, value in os.environ.items()
        if not key.startswith(("PWF_", "CLAUDE_", "CODEX_"))
        and key not in {
            "PLAN_ID", "PLANNING_DISABLED", "BASH_ENV", "ENV", "CDPATH",
            "PYTHONPATH", "PYTHONHOME",
        }
    }
    for variable, directory in {
        "HOME": "home", "USERPROFILE": "home", "XDG_CACHE_HOME": "cache",
        "XDG_CONFIG_HOME": "config", "TMPDIR": "tmp", "TMP": "tmp", "TEMP": "tmp",
    }.items():
        path = tmp_path / directory
        path.mkdir(exist_ok=True)
        env[variable] = str(path)
    env.update({
        "PWF_TRUSTED_PYTHON": str(Path(sys.executable).resolve()),
        "CLAUDE_PLUGIN_ROOT": str(REPO),
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
    })
    return root, env


def write_plan(root, *, gated, completed=True):
    first = "complete" if completed else "in_progress"
    (root / "task_plan.md").write_text(
        f"# Task Plan\n### Phase 1: Work\n**Status:** {first}\n"
        "### Phase 2: Verify\n**Status:** complete\n",
        encoding="utf-8",
    )
    if gated:
        (root / ".mode").write_text("autonomous gate\n", encoding="utf-8")
    (root / "ledger-main.jsonl").write_text(
        '{"tick":1,"event":"progress","summary":"verified"}\n', encoding="utf-8"
    )


def file_state(root):
    return {
        path.relative_to(root).as_posix(): (path.read_bytes(), path.stat().st_mtime_ns)
        for path in root.rglob("*") if path.is_file()
    }


def command(route, env, *, gate=True):
    if route == "ps-checker":
        powershell = shutil.which("powershell.exe") or shutil.which("pwsh")
        if not powershell:
            pytest.skip("PowerShell is unavailable")
        return [powershell, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                "-File", str(SCRIPTS / "check-complete.ps1"), *(["-Gate"] if gate else [])]

    if os.name == "nt":
        adapter = runpy.run_path(str(REPO / ".codex" / "hooks" / "codex_hook_adapter.py"))
        shell, path_dirs = adapter["_windows_git_bash"]()
        env["PATH"] = os.pathsep.join([*path_dirs, env.get("PATH", "")])
    else:
        shell = shutil.which("sh")
    if not shell:
        pytest.skip("POSIX sh or Git for Windows sh.exe is unavailable")
    scripts = {
        "sh-checker": [str(SCRIPTS / "check-complete.sh"), *(["--gate"] if gate else [])],
        "claude-plugin": [str(REPO / "hooks" / "claude-hook.sh"), "stop"],
        "standalone-skill": [str(SCRIPTS / "skill-hook.sh"), "--event=stop"],
        "codex": [str(REPO / ".codex" / "hooks" / "stop.sh")],
    }
    return [shell, *scripts[route]]


def invoke(route, project, *, gate=True):
    root, environment = project
    env = environment.copy()
    result = subprocess.run(
        command(route, env, gate=gate), cwd=root, env=env,
        input=json.dumps({"session_id": "quiet-completion-test", "stop_hook_active": False}),
        capture_output=True, text=True, encoding="utf-8", timeout=60, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stderr == "", result.stderr
    return result.stdout


@pytest.mark.parametrize("route", CHECKERS + HOOKS)
@pytest.mark.parametrize("gated", [False, True], ids=["legacy", "gated"])
def test_completed_automatic_checks_are_silent_and_preserve_state(project, route, gated):
    root, _ = project
    write_plan(root, gated=gated)
    # A finished plan can retain earlier gate bookkeeping. Repeated Stop
    # events must neither reset that state nor append new ledger activity.
    (root / ".stop_blocks").write_text("2\n", encoding="utf-8")
    (root / ".gate_last_ledger").write_text("1\n", encoding="utf-8")
    before = file_state(root)
    outputs = [invoke(route, project), invoke(route, project)]
    assert file_state(root) == before
    assert outputs == ["", ""]


@pytest.mark.parametrize("route", CHECKERS)
def test_explicit_completion_report_remains_available(project, route):
    root, _ = project
    write_plan(root, gated=True)
    before = file_state(root)
    output = invoke(route, project, gate=False)
    assert "ALL PHASES COMPLETE (2/2)" in output
    assert file_state(root) == before


@pytest.mark.parametrize("route", CHECKERS + HOOKS)
def test_incomplete_gated_plan_still_blocks_automatic_stop(project, route):
    root, _ = project
    write_plan(root, gated=True, completed=False)
    ledger_before = (root / "ledger-main.jsonl").read_bytes()
    output = json.loads(invoke(route, project))
    assert output["decision"] == "block"
    assert "Phase 1: Work" in output["reason"]
    assert (root / ".stop_blocks").read_text(encoding="utf-8-sig").strip() == "1"
    assert (root / "ledger-main.jsonl").read_bytes() == ledger_before


@pytest.mark.parametrize("route", CHECKERS + HOOKS)
def test_automatic_check_without_plan_is_silent(project, route):
    # A cwd with no plan is the common case for every session that never
    # opted into planning; the Stop hook must not surface a notice there.
    root, _ = project
    before = file_state(root)
    assert invoke(route, project) == ""
    assert file_state(root) == before


@pytest.mark.parametrize("route", CHECKERS)
def test_explicit_report_without_plan_keeps_notice(project, route):
    assert "No task_plan.md found" in invoke(route, project, gate=False)
