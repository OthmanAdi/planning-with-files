import json
import subprocess

from .paths import normalize_cwd, resolve_skill_dir
from .planning_files import ensure_planning_files, summarize_status


def planning_with_files_init(template: str = "default", cwd: str = "") -> str:
    project_dir = normalize_cwd(cwd)
    result = ensure_planning_files(project_dir, template=template)
    return json.dumps(result, ensure_ascii=False)


def planning_with_files_status(cwd: str = "") -> str:
    project_dir = normalize_cwd(cwd)
    result = summarize_status(project_dir)
    return json.dumps(result, ensure_ascii=False)


def planning_with_files_check_complete(cwd: str = "") -> str:
    project_dir = normalize_cwd(cwd)
    skill_root = resolve_skill_dir(project_dir)
    script = skill_root / "scripts" / "check-complete.sh"
    if not script.exists():
        return json.dumps(
            {"ok": False, "error": f"Missing script: {script}", "skill_root": str(skill_root), "complete": False},
            ensure_ascii=False,
        )
    completed = subprocess.run(
        ["sh", str(script), str(project_dir / "task_plan.md")],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(project_dir),
    )
    stdout = completed.stdout.strip()
    return json.dumps(
        {
            "ok": completed.returncode == 0,
            "returncode": completed.returncode,
            "stdout": stdout,
            "stderr": completed.stderr.strip(),
            "skill_root": str(skill_root),
            "complete": "ALL PHASES COMPLETE" in stdout,
        },
        ensure_ascii=False,
    )
