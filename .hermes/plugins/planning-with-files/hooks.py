from __future__ import annotations

from typing import Any

from .constants import PROGRESS_TAIL_LINES, READ_PREVIEW_LINES
from .hook_state import add_reminder, pop_reminders
from .paths import normalize_cwd
from .planning_files import head_lines, tail_lines


def build_user_prompt_context(project_dir) -> str:
    task_plan = project_dir / "task_plan.md"
    if not task_plan.exists():
        return ""
    parts = ["[planning-with-files] ACTIVE PLAN — current state:"]
    head = head_lines(task_plan, READ_PREVIEW_LINES)
    if head:
        parts.append(head)
    progress = tail_lines(project_dir / "progress.md", PROGRESS_TAIL_LINES)
    if progress:
        parts.append("=== recent progress ===")
        parts.append(progress)
    findings = project_dir / "findings.md"
    if findings.exists():
        parts.append("[planning-with-files] Read findings.md for research context. Continue from the current phase.")
    return "\n\n".join(parts)


def pre_llm_call(**kwargs: Any) -> dict[str, str] | None:
    project_dir = normalize_cwd()
    if not (project_dir / "task_plan.md").exists():
        return None
    user_message = str(kwargs.get("user_message", ""))
    session_id = str(kwargs.get("session_id", ""))
    reminder_messages = pop_reminders(session_id)
    context = build_user_prompt_context(project_dir)
    parts: list[str] = []
    if reminder_messages:
        parts.append("\n".join(reminder_messages))
    if context:
        parts.append(context)
    if not user_message.strip() and not kwargs.get("is_first_turn") and not reminder_messages:
        return None
    if not parts:
        return None
    return {"context": "\n\n".join(parts)}


def post_tool_call(**kwargs: Any) -> None:
    tool_name = str(kwargs.get("tool_name", ""))
    args = kwargs.get("args") or {}
    if tool_name == "write_file":
        if not args.get("path") or "content" not in args:
            return None
    elif tool_name == "patch":
        has_patch_payload = bool(args.get("patch"))
        has_replace_payload = bool(args.get("path")) and "old_string" in args and "new_string" in args
        if not (has_patch_payload or has_replace_payload):
            return None
    else:
        return None
    project_dir = normalize_cwd()
    if not (project_dir / "task_plan.md").exists():
        return None
    session_id = str(kwargs.get("session_id", ""))
    message = "[planning-with-files] Update progress.md with what you just did. If a phase is now complete, update task_plan.md status."
    add_reminder(session_id, message)
    return None
