"""Exercise interpreter fallback without changing the machine's Python/PATH."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _bash():
    if os.name == "nt":
        path = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Git/bin/bash.exe"
        if path.is_file():
            return str(path)
    bash = shutil.which("bash")
    if not bash:
        pytest.skip("bash is required for Qoder hook launch tests")
    return bash


@pytest.mark.parametrize("interpreter", ["python3", "python", "py", None])
def test_launcher_skips_broken_candidates_preserves_stdin_and_quotes_root(tmp_path, interpreter):
    plugin = tmp_path / "plugin with 'quotes' and $dollars"
    hooks = plugin / ".qoder-plugin"
    hooks.mkdir(parents=True)
    shutil.copyfile(ROOT / ".qoder-plugin/run-hook.sh", hooks / "run-hook.sh")
    (hooks / "hook_adapter.py").write_text(
        "import sys; sys.stdout.write(sys.stdin.read()); sys.exit(2)\n", encoding="utf-8"
    )
    binaries = tmp_path / "bin"
    binaries.mkdir()
    # No external commands are needed inside these wrappers or the launcher.
    real_python = str(Path(sys.executable)).replace("\\", "/").replace("'", "'\"'\"'")
    for candidate in ("python3", "python", "py"):
        script = "#!/bin/sh\n"
        if candidate == interpreter:
            if candidate == "py":
                script += '[ "$1" = "-3" ] || exit 77\nshift\n'
            script += f"exec '{real_python}' \"$@\"\n"
        else:
            script += "exit 127\n"
        path = binaries / candidate
        path.write_text(script, encoding="utf-8", newline="\n")
        path.chmod(0o755)
    payload = json.dumps({"hook_event_name": "Stop", "prompt": "keep stdin intact"})
    result = subprocess.run(
        [_bash(), str(hooks / "run-hook.sh")], input=payload,
        text=True, encoding="utf-8", capture_output=True,
        env={**os.environ, "PATH": str(binaries), "QODER_PLUGIN_ROOT": str(plugin)},
        check=False,
    )
    if interpreter is None:
        assert result.returncode == 1
        assert result.stdout == ""
        assert "require Python 3.10" in result.stderr
    else:
        assert result.returncode == 2, result.stderr
        assert result.stdout == payload
        assert result.stderr == ""


@pytest.mark.parametrize("poison_source", ["cwd", "pythonpath"])
def test_qoder_launcher_does_not_import_project_python_startup(tmp_path, poison_source):
    project = tmp_path / "project"
    project.mkdir()
    poison = project if poison_source == "cwd" else tmp_path / "poison"
    poison.mkdir(exist_ok=True)
    marker = tmp_path / "startup-executed"
    (poison / "sitecustomize.py").write_text(
        "from pathlib import Path\nPath(" + repr(str(marker)) + ").write_text('executed')\n", encoding="utf-8"
    )
    (project / "task_plan.md").write_text("### Phase 1\n- **Status:** in_progress\n", encoding="utf-8")
    (project / ".mode").write_text("autonomous gate\n", encoding="utf-8")
    env = {**os.environ, "QODER_PLUGIN_ROOT": str(ROOT)}
    if poison_source == "pythonpath":
        env["PYTHONPATH"] = str(poison)
    else:
        env.pop("PYTHONPATH", None)
    result = subprocess.run(
        [_bash(), str(ROOT / ".qoder-plugin/run-hook.sh")],
        input=json.dumps({"cwd": str(project), "hook_event_name": "Stop"}),
        text=True, encoding="utf-8", capture_output=True,
        cwd=project, env=env, check=False,
    )
    assert not marker.exists(), "Hook Python imported untrusted sitecustomize.py"
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert "Gated plan incomplete" in result.stderr


@pytest.mark.parametrize("prefix", [".", "", "relative-bin"])
def test_launcher_ignores_relative_path_interpreters(tmp_path, prefix):
    project = tmp_path / "project"
    project.mkdir()
    relative = project / "relative-bin"
    relative.mkdir()
    marker = tmp_path / "interpreter-executed"
    poison = "#!/bin/sh\nprintf poison > '" + str(marker).replace("\\", "/") + "'\nexit 0\n"
    for directory in (project, relative):
        for name in ("python3", "python", "py"):
            script = directory / name
            script.write_text(poison, encoding="utf-8", newline="\n")
            script.chmod(0o755)
    # Convert the host PATH inside bash before prepending the untrusted entry.
    result = subprocess.run(
        [_bash(), "-c", 'PATH="$PWF_TEST_PATH_PREFIX:$PATH"; export PATH; . "$QODER_PLUGIN_ROOT/.qoder-plugin/run-hook.sh"'],
        input=json.dumps({"hook_event_name": "Unknown"}),
        text=True, encoding="utf-8", capture_output=True,
        cwd=project,
        env={**os.environ, "QODER_PLUGIN_ROOT": str(ROOT), "PWF_TEST_PATH_PREFIX": prefix},
        check=False,
    )
    assert not marker.exists(), "Hook resolved a project-relative Python executable"
    assert result.returncode == 0, result.stderr


def test_descriptor_does_not_execute_project_sh(tmp_path):
    marker = tmp_path / "shell-executed"
    script = tmp_path / "sh"
    script.write_text("#!/bin/sh\nprintf poison > '" + str(marker).replace("\\", "/") + "'\nexit 0\n", encoding="utf-8", newline="\n")
    script.chmod(0o755)
    descriptor = json.loads((ROOT / "hooks/qoder-hooks.json").read_text(encoding="utf-8"))
    command = descriptor["hooks"]["SessionStart"][0]["hooks"][0]["command"]
    result = subprocess.run(
        [_bash(), "-c", 'PATH=".:$PATH"; export PATH; ' + command],
        input=json.dumps({"hook_event_name": "Unknown"}),
        text=True, encoding="utf-8", capture_output=True, cwd=tmp_path,
        env={**os.environ, "QODER_PLUGIN_ROOT": str(ROOT)}, check=False,
    )
    assert not marker.exists(), "Descriptor invoked project-local sh"
    assert result.returncode == 0, result.stderr
