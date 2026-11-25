"""An eligible plan gets one fixed notice when no interpreter is usable."""
import os
import shutil
import subprocess
from pathlib import Path

import pytest


# Both tests strip PATH to control which tools the hook can find. Git Bash on
# Windows does not honor that the same way, so they run on POSIX hosts only.
@pytest.mark.skipif(
    os.name == "nt" or not (shutil.which("sh") and shutil.which("realpath")),
    reason="requires POSIX sh and realpath",
)
def test_no_python_notice(tmp_path):
    script = Path(__file__).resolve().parents[1] / "scripts" / "inject-plan.sh"
    (tmp_path / "task_plan.md").write_text("# Private plan body\n")
    # Keep containment available even on hosts with a system Python.
    (tmp_path / "realpath").symlink_to(shutil.which("realpath"))
    result = subprocess.run(
        [shutil.which("sh"), str(script), "--context=userprompt"], cwd=tmp_path, env={"PATH": str(tmp_path)},
        capture_output=True, text=True, encoding="utf-8", check=True,
    )
    assert result.stdout == (
        "[planning-with-files] Plan injection needs Python 3.8 or newer "
        "and no usable interpreter was found — nothing injected.\n"
    )


@pytest.mark.skipif(os.name == "nt" or not shutil.which("sh"), reason="requires POSIX sh")
def test_no_canonicalizer_notice(tmp_path):
    script = Path(__file__).resolve().parents[1] / "scripts" / "inject-plan.sh"
    sh = shutil.which("sh")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    try:
        (bin_dir / Path(sh).name).symlink_to(sh)
    except OSError:
        shutil.copy2(sh, bin_dir / Path(sh).name)
    project = tmp_path / "project"
    project.mkdir()
    (project / "task_plan.md").write_text("# Private plan body\n")
    result = subprocess.run(
        [sh, str(script), "--context=userprompt"],
        cwd=project,
        env={"PATH": str(bin_dir)},
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    assert result.stdout == (
        "[planning-with-files] Plan injection could not verify the plan path: "
        "it needs realpath, readlink -f, or an absolute PWF_TRUSTED_PYTHON or "
        "PYTHON_BIN path to Python 3.8 or newer, and none was usable, so "
        "nothing was injected.\n"
    )
    for context in ("pretool", "precompact", "preflight", "validate"):
        quiet = subprocess.run(
            [sh, str(script), f"--context={context}"],
            cwd=project,
            env={"PATH": str(bin_dir)},
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )
        assert quiet.stdout == ""
