import json
import shutil
import subprocess
from pathlib import Path

from .paths import (
    MULTIPLE_PLANS_MESSAGE,
    multiple_plans_require_selector,
    normalize_cwd,
    plan_id_for,
    resolve_plan_dir,
    resolve_skill_dir,
)
from .planning_files import init_plan, phase_counts, summarize_status


def planning_with_files_init(
    template: str = "default",
    cwd: str = "",
    name: str = "",
    mode: str = "",
) -> str:
    project_dir = normalize_cwd(cwd)
    result = init_plan(project_dir, name=name or "", template=template or "default", mode=mode or "")
    return json.dumps(result, ensure_ascii=False)


def planning_with_files_status(cwd: str = "") -> str:
    project_dir = normalize_cwd(cwd)
    result = summarize_status(project_dir)
    return json.dumps(result, ensure_ascii=False)


def _python_completion_report(plan_file: Path) -> dict:
    """Fallback for hosts without ``sh`` (native Windows Hermes Desktop)."""
    counts = phase_counts(plan_file.read_text(encoding="utf-8", errors="replace"))
    complete = counts["total"] > 0 and counts["complete"] >= counts["total"]
    if complete:
        stdout = (
            f"[planning-with-files] ALL PHASES COMPLETE ({counts['complete']}/{counts['total']}). "
            "If the user has additional work, add new phases to task_plan.md before starting."
        )
    else:
        stdout = (
            f"[planning-with-files] Plan incomplete: {counts['complete']}/{counts['total']} phases complete, "
            f"{counts['in_progress']} in_progress."
        )
    return {"ok": True, "returncode": 0, "stdout": stdout, "stderr": "", "complete": complete, "route": "python"}


def planning_with_files_check_complete(cwd: str = "") -> str:
    project_dir = normalize_cwd(cwd)
    skill_root = resolve_skill_dir(project_dir)
    plan_dir = resolve_plan_dir(project_dir)
    if plan_dir is None:
        return json.dumps(
            {
                "ok": False,
                "error": (
                    MULTIPLE_PLANS_MESSAGE
                    if multiple_plans_require_selector(project_dir)
                    else "No task_plan.md found. Run planning_with_files_init first."
                ),
                "skill_root": str(skill_root),
                "complete": False,
            },
            ensure_ascii=False,
        )
    plan_file = plan_dir / "task_plan.md"
    script = skill_root / "scripts" / "check-complete.sh"
    shell = shutil.which("sh")
    if not script.exists() or shell is None:
        payload = _python_completion_report(plan_file)
        payload.update({"skill_root": str(skill_root), "plan_dir": str(plan_dir), "plan_id": plan_id_for(project_dir, plan_dir)})
        if not script.exists():
            payload["note"] = f"Missing script: {script}; evaluated in Python."
        return json.dumps(payload, ensure_ascii=False)
    try:
        completed = subprocess.run(
            [shell, str(script), str(plan_file)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            cwd=str(project_dir),
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        payload = _python_completion_report(plan_file)
        payload.update({"skill_root": str(skill_root), "plan_dir": str(plan_dir), "plan_id": plan_id_for(project_dir, plan_dir)})
        payload["note"] = f"check-complete.sh did not finish ({exc.__class__.__name__}); evaluated in Python."
        return json.dumps(payload, ensure_ascii=False)
    stdout = completed.stdout.strip()
    return json.dumps(
        {
            "ok": completed.returncode == 0,
            "returncode": completed.returncode,
            "stdout": stdout,
            "stderr": completed.stderr.strip(),
            "skill_root": str(skill_root),
            "plan_dir": str(plan_dir),
            "plan_id": plan_id_for(project_dir, plan_dir),
            "complete": "ALL PHASES COMPLETE" in stdout,
            "route": "sh",
        },
        ensure_ascii=False,
    )
