"""An eligible plan gets one fixed notice when no interpreter is usable."""
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(not (shutil.which("sh") and shutil.which("realpath")), reason="requires sh and realpath")
def test_no_python_notice(tmp_path):
    script = Path(__file__).resolve().parents[1] / "scripts" / "inject-plan.sh"
    (tmp_path / "task_plan.md").write_text("# Private plan body\n")
    # Keep containment available even on hosts with a system Python.
    (tmp_path / "realpath").symlink_to(shutil.which("realpath"))
    result = subprocess.run(
        [shutil.which("sh"), str(script), "--context=userprompt"], cwd=tmp_path, env={"PATH": str(tmp_path)},
        capture_output=True, text=True, check=True,
    )
    assert result.stdout == (
        "[planning-with-files] Plan injection needs Python 3.8 or newer "
        "and no usable interpreter was found — nothing injected.\n"
    )
