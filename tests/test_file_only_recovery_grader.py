"""Run the file-only recovery fixture's grader self-check as part of pytest.

The grading contract lives in examples/file-only-recovery/grade.py. This test
only runs it, from an unrelated working directory, and reports its output when
it fails.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
GRADER = REPO_ROOT / "examples" / "file-only-recovery" / "grade.py"


def test_grader_self_check_passes(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(GRADER), "--self-check"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    assert result.returncode == 0, (
        f"grade.py --self-check exited {result.returncode}\n"
        f"--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}"
    )
    assert result.stdout.splitlines()[-1:] == ["self-check: pass"], result.stdout
