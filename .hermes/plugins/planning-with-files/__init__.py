import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

PLUGIN_DIR = Path(__file__).resolve().parent
PLANNING_FILES = ("task_plan.md", "findings.md", "progress.md")


def _find_repo_root(start: Path) -> Path:
    explicit = os.environ.get("PLANNING_WITH_FILES_REPO_ROOT", "").strip()
    if explicit:
        candidate = Path(explicit).expanduser().resolve()
        if (candidate / "templates").is_dir() and (candidate / "scripts").is_dir():
            return candidate
    for candidate in [start, *start.parents]:
        if (candidate / "templates").is_dir() and (candidate / "scripts").is_dir():
            return candidate
    cwd = Path.cwd().resolve()
    for candidate in [cwd, *cwd.parents]:
        if (candidate / "templates").is_dir() and (candidate / "scripts").is_dir():
            return candidate
    return start


REPO_ROOT = _find_repo_root(PLUGIN_DIR)
TEMPLATES_DIR = REPO_ROOT / "templates"
SCRIPTS_DIR = REPO_ROOT / "scripts"
READ_PREVIEW_LINES = 50
PROGRESS_TAIL_LINES = 20
PLAN_PREVIEW_LINES = 30
WATCHED_TOOLS = {
    "read_file",
    "write_file",
    "patch",
    "search_files",
    "terminal",
    "browser_navigate",
    "browser_snapshot",
    "browser_click",
    "browser_type",
    "browser_scroll",
    "browser_press",
    "web_search",
}


def _normalize_cwd(cwd: str | None = None) -> Path:
    candidate = cwd or str(Path.cwd()) or os.environ.get("PWD") or "."
    return Path(candidate).expanduser().resolve()


def _tail_lines(path: Path, limit: int) -> str:
    if not path.exists():
        return ""
    lines = path.read_text(encoding="utf-8").splitlines()
    return "\n".join(lines[-limit:])


def _head_lines(path: Path, limit: int) -> str:
    if not path.exists():
        return ""
    lines = path.read_text(encoding="utf-8").splitlines()
    return "\n".join(lines[:limit])


def _ensure_planning_files(project_dir: Path, template: str = "default") -> dict[str, Any]:
    created: list[str] = []
    for name in PLANNING_FILES:
        dest = project_dir / name
        if dest.exists():
            continue
        template_name = f"{name}"
        if template != "default":
            prefixed = TEMPLATES_DIR / f"{template}_{name}"
            source = prefixed if prefixed.exists() else TEMPLATES_DIR / template_name
        else:
            source = TEMPLATES_DIR / template_name
        if source.exists():
            shutil.copy2(source, dest)
        else:
            dest.write_text("", encoding="utf-8")
        created.append(name)
    return {
        "project_dir": str(project_dir),
        "created": created,
        "existing": [name for name in PLANNING_FILES if (project_dir / name).exists()],
    }


def _phase_counts(task_plan: str) -> dict[str, int]:
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
        for marker, key in (("[complete]", "complete"), ("[in_progress]", "in_progress"), ("[pending]", "pending")):
            counts[key] = task_plan.count(marker)
        counts["total"] = counts["complete"] + counts["in_progress"] + counts["pending"]
    return counts


def _extract_current_phase(task_plan: str) -> str:
    for line in task_plan.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("## current phase"):
            return stripped
    for line in task_plan.splitlines():
        stripped = line.strip()
        if stripped.startswith("### Phase") and "in_progress" in stripped.lower():
            return stripped
    for line in task_plan.splitlines():
        stripped = line.strip()
        if stripped.startswith("### Phase"):
            return stripped
    return "No phase found"


def _summarize_status(project_dir: Path) -> dict[str, Any]:
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
    counts = _phase_counts(task_plan)
    error_rows = sum(1 for line in task_plan.splitlines() if line.strip().startswith("|") and "Error" not in line)
    return {
        "exists": True,
        "project_dir": str(project_dir),
        "current_phase": _extract_current_phase(task_plan),
        "counts": counts,
        "files": {
            "task_plan.md": task_plan_path.exists(),
            "findings.md": findings_path.exists(),
            "progress.md": progress_path.exists(),
        },
        "recent_progress": _tail_lines(progress_path, PROGRESS_TAIL_LINES),
        "plan_preview": _head_lines(task_plan_path, PLAN_PREVIEW_LINES),
        "errors_logged": error_rows,
    }


def _run_check_complete(project_dir: Path) -> dict[str, Any]:
    script = SCRIPTS_DIR / "check-complete.sh"
    if not script.exists():
        return {"ok": False, "error": f"Missing script: {script}"}
    completed = subprocess.run(
        ["sh", str(script), str(project_dir / "task_plan.md")],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(project_dir),
    )
    return {
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def planning_with_files_init(template: str = "default", cwd: str = "") -> str:
    project_dir = _normalize_cwd(cwd)
    result = _ensure_planning_files(project_dir, template=template)
    return json.dumps(result, ensure_ascii=False)


def planning_with_files_status(cwd: str = "") -> str:
    project_dir = _normalize_cwd(cwd)
    result = _summarize_status(project_dir)
    return json.dumps(result, ensure_ascii=False)


def planning_with_files_check_complete(cwd: str = "") -> str:
    project_dir = _normalize_cwd(cwd)
    result = _run_check_complete(project_dir)
    return json.dumps(result, ensure_ascii=False)


def _tool_targets_planning(tool_name: str, args: dict[str, Any]) -> bool:
    if tool_name not in WATCHED_TOOLS:
        return False
    serialized = json.dumps(args, ensure_ascii=False)
    return any(name in serialized for name in PLANNING_FILES) or tool_name in {"search_files", "terminal", "browser_navigate", "web_search"}


def _build_context(project_dir: Path) -> str:
    task_plan = project_dir / "task_plan.md"
    if not task_plan.exists():
        return ""
    parts = ["[planning-with-files] ACTIVE PLAN — current state:"]
    head = _head_lines(task_plan, READ_PREVIEW_LINES)
    if head:
        parts.append(head)
    progress = _tail_lines(project_dir / "progress.md", PROGRESS_TAIL_LINES)
    if progress:
        parts.append("=== recent progress ===")
        parts.append(progress)
    findings = project_dir / "findings.md"
    if findings.exists():
        parts.append("[planning-with-files] Read findings.md for research context when making decisions.")
    return "\n\n".join(parts)


def _pre_llm_call(**kwargs: Any) -> dict[str, str] | None:
    project_dir = _normalize_cwd()
    if not (project_dir / "task_plan.md").exists():
        return None
    user_message = str(kwargs.get("user_message", ""))
    tool_name = str(kwargs.get("tool_name", ""))
    args = kwargs.get("args")
    if tool_name and isinstance(args, dict) and not _tool_targets_planning(tool_name, args):
        return None
    if not user_message.strip() and not kwargs.get("is_first_turn"):
        return None
    context = _build_context(project_dir)
    if not context:
        return None
    return {"context": context}


def _register_tools(ctx: Any) -> None:
    ctx.register_tool(
        name="planning_with_files_init",
        toolset="terminal",
        schema={
            "name": "planning_with_files_init",
            "description": "Create planning-with-files markdown files in the current project directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "template": {"type": "string", "description": "Template name, e.g. default or analytics."},
                    "cwd": {"type": "string", "description": "Target project directory. Defaults to current working directory."},
                },
            },
        },
        handler=lambda args, **kw: planning_with_files_init(
            template=args.get("template", "default"),
            cwd=args.get("cwd", ""),
        ),
        description="Initialize planning-with-files state files.",
    )
    ctx.register_tool(
        name="planning_with_files_status",
        toolset="terminal",
        schema={
            "name": "planning_with_files_status",
            "description": "Summarize current planning file status for the active project.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cwd": {"type": "string", "description": "Target project directory. Defaults to current working directory."},
                },
            },
        },
        handler=lambda args, **kw: planning_with_files_status(cwd=args.get("cwd", "")),
        description="Show planning-with-files status summary.",
    )
    ctx.register_tool(
        name="planning_with_files_check_complete",
        toolset="terminal",
        schema={
            "name": "planning_with_files_check_complete",
            "description": "Run the planning-with-files completion check script.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cwd": {"type": "string", "description": "Target project directory. Defaults to current working directory."},
                },
            },
        },
        handler=lambda args, **kw: planning_with_files_check_complete(cwd=args.get("cwd", "")),
        description="Check whether all planning phases are complete.",
    )


def register(ctx: Any) -> None:
    _register_tools(ctx)
    ctx.register_hook("pre_llm_call", _pre_llm_call)
