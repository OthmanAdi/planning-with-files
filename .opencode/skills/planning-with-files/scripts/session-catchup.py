#!/usr/bin/env python3
"""
Session Catchup Script for planning-with-files

Analyzes the previous session to find unsynced context after the last
planning file update. Designed to run on SessionStart.

Usage: python3 session-catchup.py [project-path]
"""

import json
import sys
import os
from pathlib import Path
from typing import List, Dict, Optional, Tuple


PLANNING_FILES = ['task_plan.md', 'progress.md', 'findings.md']


def get_project_dir(project_path: str) -> Path:
    """Convert project path to OpenCode's storage path format."""
    # Normalize to an absolute path to ensure a stable representation
    # .as_posix() handles '\' -> '/' conversion on Windows automatically
    resolved_str = Path(project_path).resolve().as_posix()
    
    # Sanitize path: replace separators with '-', remove ':' (Windows drives)
    sanitized = resolved_str.replace('/', '-').replace(':', '')

    # Apply legacy naming convention: leading '-' and '_' -> '-'
    if not sanitized.startswith('-'):
        sanitized = '-' + sanitized
    sanitized_name = sanitized.replace('_', '-')

    # 1. Check Legacy Location first (~/.opencode/sessions/...)
    legacy_dir = Path.home() / '.opencode' / 'sessions' / sanitized_name
    if legacy_dir.is_dir():
        return legacy_dir

    # 2. Standard Layout
    data_root_env = os.getenv('OPENCODE_DATA_DIR')
    if data_root_env:
        data_root = Path(data_root_env)
    else:
        # Respect XDG_DATA_HOME if set, otherwise use default
        xdg_root = os.getenv('XDG_DATA_HOME')
        if xdg_root:
            data_root = Path(xdg_root) / 'opencode' / 'storage'
        else:
            data_root = Path.home() / '.local' / 'share' / 'opencode' / 'storage'

    return data_root / 'session' / sanitized_name


def get_sessions_sorted(project_dir: Path) -> List[Path]:
    """Get all session files sorted by modification time (newest first)."""
    # Support both legacy JSONL (*.jsonl) and standard JSON (*.json) session files.
    sessions = list(project_dir.glob('*.jsonl')) + list(project_dir.glob('*.json'))
    # Deduplicate in case of overlaps and filter out agent-specific sessions.
    unique_sessions = {s for s in sessions}
    main_sessions = [s for s in unique_sessions if not s.name.startswith('agent-')]
    return sorted(main_sessions, key=lambda p: p.stat().st_mtime, reverse=True)


def parse_session_messages(session_file: Path) -> List[Dict]:
    """Parse all messages from a session file, preserving order."""
    messages: List[Dict] = []

    # First, try to parse the entire file as JSON (for *.json session files).
    try:
        with open(session_file, 'r') as f:
            content = f.read()
        if content.strip():
            data = json.loads(content)
            if isinstance(data, list):
                for idx, item in enumerate(data):
                    if isinstance(item, dict):
                        item['_line_num'] = idx
                        messages.append(item)
            elif isinstance(data, dict):
                # Some formats may wrap messages in a top-level object.
                msg_list = data.get('messages')
                if isinstance(msg_list, list):
                    for idx, item in enumerate(msg_list):
                        if isinstance(item, dict):
                            item['_line_num'] = idx
                            messages.append(item)
    except json.JSONDecodeError:
        # Fall through to JSONL parsing if full-file JSON parsing fails.
        messages = []

    if messages:
        return messages

    # Fallback: treat file as JSONL (one JSON object per line), the original behavior.
    messages = []
    with open(session_file, 'r') as f:
        for line_num, line in enumerate(f):
            try:
                data = json.loads(line)
                if isinstance(data, dict):
                    data['_line_num'] = line_num
                    messages.append(data)
            except json.JSONDecodeError:
                # Ignore malformed lines to be resilient to partial writes.
                # Some session log lines may be incomplete or non-JSON; skip them
                pass
    return messages


def find_last_planning_update(messages: List[Dict]) -> Tuple[int, Optional[str]]:
    """
    Find the last time a planning file was written/edited.
    Returns (line_number, filename) or (-1, None) if not found.
    """
    last_update_line = -1
    last_update_file = None

    for msg in messages:
        msg_type = msg.get('type')

        if msg_type == 'assistant':
            content = msg.get('message', {}).get('content', [])
            if isinstance(content, list):
                for item in content:
                    if item.get('type') == 'tool_use':
                        tool_name = item.get('name', '')
                        tool_input = item.get('input', {})

                        if tool_name in ('Write', 'Edit'):
                            file_path = tool_input.get('file_path', '')
                            for pf in PLANNING_FILES:
                                if file_path.endswith(pf):
                                    last_update_line = msg['_line_num']
                                    last_update_file = pf

    return last_update_line, last_update_file


def extract_messages_after(messages: List[Dict], after_line: int) -> List[Dict]:
    """Extract conversation messages after a certain line number."""
    result = []
    for msg in messages:
        if msg['_line_num'] <= after_line:
            continue

        msg_type = msg.get('type')
        is_meta = msg.get('isMeta', False)

        if msg_type == 'user' and not is_meta:
            content = msg.get('message', {}).get('content', '')
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get('type') == 'text':
                        content = item.get('text', '')
                        break
                else:
                    content = ''

            if content and isinstance(content, str):
                if content.startswith(('<local-command', '<command-', '<task-notification')):
                    continue
                if len(content) > 20:
                    result.append({'role': 'user', 'content': content, 'line': msg['_line_num']})

        elif msg_type == 'assistant':
            msg_content = msg.get('message', {}).get('content', '')
            text_content = ''
            tool_uses = []

            if isinstance(msg_content, str):
                text_content = msg_content
            elif isinstance(msg_content, list):
                for item in msg_content:
                    if item.get('type') == 'text':
                        text_content = item.get('text', '')
                    elif item.get('type') == 'tool_use':
                        tool_name = item.get('name', '')
                        tool_input = item.get('input', {})
                        if tool_name == 'Edit':
                            tool_uses.append(f"Edit: {tool_input.get('file_path', 'unknown')}")
                        elif tool_name == 'Write':
                            tool_uses.append(f"Write: {tool_input.get('file_path', 'unknown')}")
                        elif tool_name == 'Bash':
                            cmd = tool_input.get('command', '')[:80]
                            tool_uses.append(f"Bash: {cmd}")
                        else:
                            tool_uses.append(f"{tool_name}")

            if text_content or tool_uses:
                result.append({
                    'role': 'assistant',
                    'content': text_content[:600] if text_content else '',
                    'tools': tool_uses,
                    'line': msg['_line_num']
                })

    return result


def main():
    project_path = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    project_dir = get_project_dir(project_path)

    # Check if planning files exist (indicates active task)
    has_planning_files = any(
        Path(project_path, f).exists() for f in PLANNING_FILES
    )
    if not has_planning_files:
        # No planning files in this project; skip catchup to avoid noise
        return

    if not project_dir.exists():
        # No previous sessions, nothing to catch up on
        return

    sessions = get_sessions_sorted(project_dir)
    if len(sessions) < 1:
        return

    # Find a substantial previous session
    target_session = None
    for session in sessions:
        if session.stat().st_size > 5000:
            target_session = session
            break

    if not target_session:
        return

    messages = parse_session_messages(target_session)
    last_update_line, last_update_file = find_last_planning_update(messages)

    # Only output if there's unsynced content
    if last_update_line < 0:
        messages_after = extract_messages_after(messages, len(messages) - 30)
    else:
        messages_after = extract_messages_after(messages, last_update_line)

    if not messages_after:
        return

    # Output catchup report
    print("\n[planning-with-files] SESSION CATCHUP DETECTED")
    print(f"Previous session: {target_session.stem}")

    if last_update_line >= 0:
        print(f"Last planning update: {last_update_file} at message #{last_update_line}")
        print(f"Unsynced messages: {len(messages_after)}")
    else:
        print("No planning file updates found in previous session")

    print("\n--- UNSYNCED CONTEXT ---")
    for msg in messages_after[-15:]:  # Last 15 messages
        if msg['role'] == 'user':
            print(f"USER: {msg['content'][:300]}")
        else:
            if msg.get('content'):
                print(f"OPENCODE: {msg['content'][:300]}")
            if msg.get('tools'):
                print(f"  Tools: {', '.join(msg['tools'][:4])}")

    print("\n--- RECOMMENDED ---")
    print("1. Run: git diff --stat")
    print("2. Read: task_plan.md, progress.md, findings.md")
    print("3. Update planning files based on above context")
    print("4. Continue with task")


if __name__ == '__main__':
    main()
