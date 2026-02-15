#!/usr/bin/env python3
"""
Session Catchup Script for planning-with-files

Analyzes the previous session to find unsynced context after the last
planning file update. Designed to run on SessionStart.

Usage: python3 session-catchup.py [project-path]
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

PLANNING_FILES = ["task_plan.md", "progress.md", "findings.md"]


def get_project_dir(project_path: str) -> Path:
    """Convert project path to Claude's storage path format."""
    sanitized = project_path.replace("/", "-")
    if not sanitized.startswith("-"):
        sanitized = "-" + sanitized
    sanitized = sanitized.replace("_", "-")

    codex_path = Path.home() / ".codex" / "projects" / sanitized
    claude_path = Path.home() / ".claude" / "projects" / sanitized

    if codex_path.exists():
        return codex_path
    if claude_path.exists():
        return claude_path
    return codex_path


def get_active_plan_dir(project_path: Path) -> Optional[Path]:
    """Resolve active plan directory from ./.planning/.active_plan, fallback to latest plan dir."""
    plan_root = project_path / ".planning"
    active_file = plan_root / ".active_plan"

    env_plan_id = os.environ.get("PLAN_ID", "").strip()
    if env_plan_id:
        candidate = plan_root / env_plan_id
        if candidate.exists() and candidate.is_dir():
            return candidate

    if active_file.exists():
        plan_id = active_file.read_text(encoding="utf-8").strip()
        if plan_id:
            candidate = plan_root / plan_id
            if candidate.exists() and candidate.is_dir():
                return candidate

    if not plan_root.exists() or not plan_root.is_dir():
        return None

    dirs = [d for d in plan_root.iterdir() if d.is_dir()]
    if not dirs:
        return None
    return sorted(dirs, key=lambda p: p.stat().st_mtime, reverse=True)[0]


def get_sessions_sorted(project_dir: Path) -> List[Path]:
    """Get all session files sorted by modification time (newest first)."""
    sessions = list(project_dir.glob("*.jsonl"))
    main_sessions = [s for s in sessions if not s.name.startswith("agent-")]
    return sorted(main_sessions, key=lambda p: p.stat().st_mtime, reverse=True)


def parse_session_messages(session_file: Path) -> List[Dict]:
    """Parse all messages from a session file, preserving order."""
    messages: List[Dict] = []
    with open(session_file, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f):
            try:
                data = json.loads(line)
                data["_line_num"] = line_num
                messages.append(data)
            except json.JSONDecodeError:
                continue
    return messages


def _matches_active_plan(file_path: str, active_plan_dir: Optional[Path]) -> bool:
    """Check whether tool-edited file belongs to active plan when active plan is known."""
    if not file_path:
        return False

    normalized = file_path.replace("\\", "/")
    if active_plan_dir is None:
        return any(normalized.endswith(pf) for pf in PLANNING_FILES)

    plan_id = active_plan_dir.name
    plan_fragment_abs = f"/.planning/{plan_id}/"
    plan_fragment_rel = f".planning/{plan_id}/"
    active_prefix = str(active_plan_dir).replace("\\", "/").rstrip("/") + "/"

    if plan_fragment_abs in normalized or normalized.startswith(plan_fragment_rel):
        return any(normalized.endswith(pf) for pf in PLANNING_FILES)
    if normalized.startswith(active_prefix):
        return any(normalized.endswith(pf) for pf in PLANNING_FILES)

    return False


def find_last_planning_update_for_active_plan(
    messages: List[Dict], active_plan_dir: Optional[Path]
) -> Tuple[int, Optional[str]]:
    """
    Find last planning-file update scoped to active plan.
    Falls back to any planning update only when active plan cannot be resolved.
    """
    last_update_line = -1
    last_update_path = None

    for msg in messages:
        if msg.get("type") != "assistant":
            continue

        content = msg.get("message", {}).get("content", [])
        if not isinstance(content, list):
            continue

        for item in content:
            if item.get("type") != "tool_use":
                continue
            if item.get("name") not in ("Write", "Edit"):
                continue

            tool_input = item.get("input", {})
            file_path = str(tool_input.get("file_path", ""))
            if _matches_active_plan(file_path, active_plan_dir):
                last_update_line = msg["_line_num"]
                last_update_path = file_path

    return last_update_line, last_update_path


def extract_messages_after(messages: List[Dict], after_line: int) -> List[Dict]:
    """Extract conversation messages after a certain line number."""
    result: List[Dict] = []
    for msg in messages:
        if msg["_line_num"] <= after_line:
            continue

        msg_type = msg.get("type")
        is_meta = msg.get("isMeta", False)

        if msg_type == "user" and not is_meta:
            content = msg.get("message", {}).get("content", "")
            if isinstance(content, list):
                extracted = ""
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        extracted = item.get("text", "")
                        break
                content = extracted

            if content and isinstance(content, str):
                if content.startswith(("<local-command", "<command-", "<task-notification")):
                    continue
                if len(content) > 20:
                    result.append(
                        {"role": "user", "content": content, "line": msg["_line_num"]}
                    )

        elif msg_type == "assistant":
            msg_content = msg.get("message", {}).get("content", "")
            text_content = ""
            tool_uses: List[str] = []

            if isinstance(msg_content, str):
                text_content = msg_content
            elif isinstance(msg_content, list):
                for item in msg_content:
                    if item.get("type") == "text":
                        text_content = item.get("text", "")
                    elif item.get("type") == "tool_use":
                        tool_name = item.get("name", "")
                        tool_input = item.get("input", {})
                        if tool_name in ("Edit", "Write"):
                            tool_uses.append(
                                f"{tool_name}: {tool_input.get('file_path', 'unknown')}"
                            )
                        elif tool_name == "Bash":
                            cmd = str(tool_input.get("command", ""))[:80]
                            tool_uses.append(f"Bash: {cmd}")
                        else:
                            tool_uses.append(f"{tool_name}")

            if text_content or tool_uses:
                result.append(
                    {
                        "role": "assistant",
                        "content": text_content[:600] if text_content else "",
                        "tools": tool_uses,
                        "line": msg["_line_num"],
                    }
                )

    return result


def main() -> None:
    project_path_str = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    project_path = Path(project_path_str).resolve()
    project_dir = get_project_dir(str(project_path))
    active_plan_dir = get_active_plan_dir(project_path)

    if not project_dir.exists():
        return

    sessions = get_sessions_sorted(project_dir)
    if not sessions:
        return

    target_session = None
    for session in sessions:
        if session.stat().st_size > 5000:
            target_session = session
            break

    if target_session is None:
        return

    messages = parse_session_messages(target_session)
    last_update_line, last_update_path = find_last_planning_update_for_active_plan(
        messages, active_plan_dir
    )

    if last_update_line < 0:
        messages_after = extract_messages_after(messages, len(messages) - 30)
    else:
        messages_after = extract_messages_after(messages, last_update_line)

    if not messages_after:
        return

    print("\n[planning-with-files] SESSION CATCHUP DETECTED")
    print(f"Previous session: {target_session.stem}")

    if last_update_line >= 0:
        print(
            f"Last planning update: {last_update_path or '(unknown)'} at message #{last_update_line}"
        )
        print(f"Unsynced messages: {len(messages_after)}")
    else:
        print("No planning file updates found in previous session")

    print("\n--- UNSYNCED CONTEXT ---")
    for msg in messages_after[-15:]:
        if msg["role"] == "user":
            print(f"USER: {msg['content'][:300]}")
        else:
            if msg.get("content"):
                print(f"CLAUDE: {msg['content'][:300]}")
            if msg.get("tools"):
                print(f"  Tools: {', '.join(msg['tools'][:4])}")

    print("\n--- RECOMMENDED ---")
    print("1. Run: git diff --stat")
    if active_plan_dir:
        print(
            f"2. Read: {active_plan_dir}/task_plan.md, {active_plan_dir}/progress.md, {active_plan_dir}/findings.md"
        )
    else:
        print("2. Read: .planning/<active_plan_id>/task_plan.md, progress.md, findings.md")
    print("3. Update planning files based on above context")
    print("4. Continue with task")


if __name__ == "__main__":
    main()
