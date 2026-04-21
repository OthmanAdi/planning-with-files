import shutil
from pathlib import Path
from typing import Any

from .constants import PLANNING_FILES, PLAN_PREVIEW_LINES, PROGRESS_TAIL_LINES
from .paths import resolve_repo_root


def tail_lines(path: Path, limit: int) -> str:
    if not path.exists():
        return ""
    lines = path.read_text(encoding="utf-8").splitlines()
    return "\n".join(lines[-limit:])


def head_lines(path: Path, limit: int) -> str:
    if not path.exists():
        return ""
    lines = path.read_text(encoding="utf-8").splitlines()
    return "\n".join(lines[:limit])


def ensure_planning_files(project_dir: Path, template: str = "default") -> dict[str, Any]:
    repo_root = resolve_repo_root(project_dir)
    templates_dir = repo_root / "templates"
    created: list[str] = []
    for name in PLANNING_FILES:
        dest = project_dir / name
        if dest.exists():
            continue
        template_name = f"{name}"
        if template != "default":
            prefixed = templates_dir / f"{template}_{name}"
            source = prefixed if prefixed.exists() else templates_dir / template_name
        else:
            source = templates_dir / template_name
        if source.exists():
            shutil.copy2(source, dest)
        else:
            dest.write_text("", encoding="utf-8")
        created.append(name)
    return {
        "project_dir": str(project_dir),
        "created": created,
        "existing": [name for name in PLANNING_FILES if (project_dir / name).exists()],
        "repo_root": str(repo_root),
    }


def phase_counts(task_plan: str) -> dict[str, int]:
    counts = {"complete": 0, "in_progress": 0, "pending": 0, "failed": 0, "total": 0}
    for line in task_plan.splitlines():
        normalized = line.strip().lower()
        if normalized.startswith("### phase"):
            counts["total"] += 1
        if "**status:**" not in normalized:
            continue
        if "complete" in normalized:
            counts["complete"] += 1
        elif "in_progress" in normalized:
            counts["in_progress"] += 1
        elif "failed" in normalized or "blocked" in normalized:
            counts["failed"] += 1
        elif "pending" in normalized:
            counts["pending"] += 1
    if counts["total"] == 0:
        for line in task_plan.splitlines():
            stripped = line.strip()
            if not (stripped.startswith("|") and stripped.endswith("|")):
                continue
            cells = [cell.strip().lower() for cell in stripped.strip("|").split("|")]
            if len(cells) < 2 or cells[0] in {"phase", "error"} or set(cells[0]) == {"-"}:
                continue
            status = cells[1]
            if status in counts:
                counts[status] += 1
                counts["total"] += 1
        if counts["total"] == 0:
            for marker, key in (("[complete]", "complete"), ("[in_progress]", "in_progress"), ("[pending]", "pending")):
                counts[key] = task_plan.count(marker)
            counts["total"] = counts["complete"] + counts["in_progress"] + counts["pending"]
    return counts


def count_error_rows(task_plan: str) -> int:
    in_errors_section = False
    rows = 0
    for line in task_plan.splitlines():
        stripped = line.strip()
        lowered = stripped.lower()
        if lowered.startswith("## errors encountered"):
            in_errors_section = True
            continue
        if in_errors_section and stripped.startswith("## "):
            break
        if not in_errors_section:
            continue
        if not (stripped.startswith("|") and stripped.endswith("|")):
            continue
        cells = [cell.strip().lower() for cell in stripped.strip("|").split("|")]
        if not cells or cells[0] == "error" or set(cells[0]) == {"-"}:
            continue
        rows += 1
    return rows


def extract_current_phase(task_plan: str) -> str:
    lines = task_plan.splitlines()
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.lower() == "## current phase":
            for next_line in lines[idx + 1 :]:
                candidate = next_line.strip()
                if not candidate or candidate.startswith("<!--"):
                    continue
                if candidate.endswith("-->") or candidate.startswith("WHAT:") or candidate.startswith("WHY:") or candidate.startswith("EXAMPLE:"):
                    continue
                return candidate
            return stripped
    current_phase_name = None
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("### Phase"):
            current_phase_name = stripped
        if "**status:**" in stripped.lower() and "in_progress" in stripped.lower() and current_phase_name:
            return current_phase_name
    if current_phase_name is None:
        for line in lines:
            stripped = line.strip()
            if not (stripped.startswith("|") and stripped.endswith("|")):
                continue
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            if len(cells) < 2 or cells[0].lower() == "phase" or set(cells[0]) == {"-"}:
                continue
            if cells[1].lower() == "in_progress":
                return cells[0]
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("### Phase"):
            return stripped
    return "No phase found"


def summarize_status(project_dir: Path) -> dict[str, Any]:
    task_plan_path = project_dir / "task_plan.md"
    findings_path = project_dir / "findings.md"
    progress_path = project_dir / "progress.md"
    if not task_plan_path.exists():
        return {
            "exists": False,
            "message": "No planning files found. Run planning_with_files_init first.",
            "files": {
                "task_plan.md": task_plan_path.exists(),
                "findings.md": findings_path.exists(),
                "progress.md": progress_path.exists(),
            },
        }
    task_plan = task_plan_path.read_text(encoding="utf-8")
    counts = phase_counts(task_plan)
    return {
        "exists": True,
        "project_dir": str(project_dir),
        "current_phase": extract_current_phase(task_plan),
        "counts": counts,
        "files": {
            "task_plan.md": task_plan_path.exists(),
            "findings.md": findings_path.exists(),
            "progress.md": progress_path.exists(),
        },
        "recent_progress": tail_lines(progress_path, PROGRESS_TAIL_LINES),
        "plan_preview": head_lines(task_plan_path, PLAN_PREVIEW_LINES),
        "errors_logged": count_error_rows(task_plan),
    }
