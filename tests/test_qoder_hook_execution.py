from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HOOKS = json.loads(
    (ROOT / "hooks" / "qoder-hooks.json").read_text(encoding="utf-8")
)["hooks"]


def _hook(event: str) -> dict[str, object]:
    return HOOKS[event][0]["hooks"][0]


def _run_hook(event: str, payload: dict[str, object], cwd: Path):
    hook = _hook(event)
    bash = shutil.which("bash")
    if os.name == "nt":
        git_bash = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Git/bin/bash.exe"
        if git_bash.is_file():
            bash = str(git_bash)
    assert bash is not None, "Qoder hooks require bash"
    return subprocess.run(
        [bash, "-c", str(hook["command"])],
        input=json.dumps(payload), text=True, encoding="utf-8",
        capture_output=True, cwd=cwd,
        env={**os.environ, "QODER_PLUGIN_ROOT": str(ROOT)}, check=False,
    )


def _project(tmp_path: Path) -> Path:
    tmp_path.joinpath("task_plan.md").write_text(
        "# Task Plan\n\n### Phase 1\n\n- **Status:** in_progress\n",
        encoding="utf-8",
    )
    tmp_path.joinpath("findings.md").write_text(
        "# Findings\n\n- Qoder fixture.\n",
        encoding="utf-8",
    )
    tmp_path.joinpath("progress.md").write_text(
        "# Progress\n\n- Running Qoder hooks.\n",
        encoding="utf-8",
    )
    return tmp_path


def test_qoder_executes_every_declared_hook_and_emits_valid_output(tmp_path: Path):
    project = _project(tmp_path)
    payloads = {
        "SessionStart": {"source": "startup", "model": "Auto"},
        "UserPromptSubmit": {"prompt": "continue"},
        "PreToolUse": {
            "tool_name": "Read",
            "tool_input": {"file_path": str(project / "task_plan.md")},
        },
        "PermissionRequest": {
            "tool_name": "Bash",
            "tool_input": {"command": "pwd"},
        },
        "PostToolUse": {
            "tool_name": "Write",
            "tool_input": {"file_path": str(project / "progress.md")},
            "tool_response": {"success": True},
        },
        "PreCompact": {"trigger": "auto"},
        "Stop": {"stop_hook_active": False},
    }

    outputs = {}
    for event, fields in payloads.items():
        payload = {"cwd": str(project), "hook_event_name": event, **fields}
        result = _run_hook(event, payload, project)
        assert result.returncode == 0, (event, result.stderr)
        assert result.stdout.strip(), event
        outputs[event] = json.loads(result.stdout)

    assert outputs["SessionStart"]["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "ACTIVE PLAN" in outputs["SessionStart"]["hookSpecificOutput"]["additionalContext"]
    assert outputs["UserPromptSubmit"]["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
    assert outputs["PreToolUse"]["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
    assert "Active plan detected" in outputs["PermissionRequest"]["systemMessage"]
    assert outputs["PostToolUse"]["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
    assert outputs["PreCompact"]["continue"] is True
    assert "Task in progress" in outputs["Stop"]["systemMessage"]


def test_qoder_gated_stop_uses_exit_two_and_stderr(tmp_path: Path):
    project = _project(tmp_path)
    (project / ".mode").write_text("autonomous gate\n", encoding="utf-8")
    result = _run_hook("Stop", {"cwd": str(project), "hook_event_name": "Stop", "stop_hook_active": False}, project)
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert "Gated plan incomplete" in result.stderr
    assert result.stdout == ""


def test_qoder_recursive_stop_does_not_block(tmp_path: Path):
    project = _project(tmp_path)
    (project / ".mode").write_text("autonomous gate\n", encoding="utf-8")
    result = _run_hook("Stop", {"cwd": str(project), "hook_event_name": "Stop", "stop_hook_active": True}, project)
    assert result.returncode == 0, result.stderr
    assert "decision" not in json.loads(result.stdout)


def test_qoder_completed_plan_does_not_block(tmp_path: Path):
    project = _project(tmp_path)
    (project / "task_plan.md").write_text("### Phase 1\n- **Status:** complete\n", encoding="utf-8")
    (project / ".mode").write_text("autonomous gate\n", encoding="utf-8")
    result = _run_hook("Stop", {"cwd": str(project), "hook_event_name": "Stop", "stop_hook_active": False}, project)
    assert result.returncode == 0, result.stderr
    assert not result.stdout.strip()
