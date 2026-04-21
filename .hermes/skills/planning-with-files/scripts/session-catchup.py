#!/usr/bin/env python3
"""
Session Catchup Script for planning-with-files

Session-agnostic scanning: finds the most recent planning file update across
ALL sessions, then collects all conversation from that point forward through
all subsequent sessions until now.

Supports multiple AI IDEs:
- Claude Code (.claude/projects/)
- OpenCode (.local/share/opencode/storage/)

Usage: python3 session-catchup.py [project-path]
"""

import json
import sys
import os
from pathlib import Path
from typing import List, Dict, Optional, Tuple

PLANNING_FILES = ['task_plan.md', 'progress.md', 'findings.md']


def detect_ide() -> str:
    """
    Detect which IDE is being used based on environment and file structure.
    Returns 'claude-code', 'opencode', or 'unknown'.
    """
    # Check for OpenCode environment
    if os.environ.get('OPENCODE_DATA_DIR'):
        return 'opencode'

    # Check for Claude Code directory
    claude_dir = Path.home() / '.claude'
    if claude_dir.exists():
        return 'claude-code'

    # Check for OpenCode directory
    opencode_dir = Path.home() / '.local' / 'share' / 'opencode'
    if opencode_dir.exists():
        return 'opencode'

    return 'unknown'


def get_project_dir_claude(project_path: str) -> Path:
    """Convert project path to Claude's storage path format."""
    sanitized = project_path.replace('/', '-')
    if not sanitized.startswith('-'):
        sanitized = '-' + sanitized
    sanitized = sanitized.replace('_', '-')
    return Path.home() / '.claude' / 'projects' / sanitized


def get_project_dir_opencode(project_path: str) -> Optional[Path]:
    """
    Get OpenCode session storage directory.
    OpenCode uses: ~/.local/share/opencode/storage/session/{projectHash}/

    Note: OpenCode's structure is different - this function returns the storage root.
    Session discovery happens differently in OpenCode.
    """
    data_dir = os.environ.get('OPENCODE_DATA_DIR',
                               str(Path.home() / '.local' / 'share' / 'opencode'))
    storage_dir = Path(data_dir) / 'storage'

    if not storage_dir.exists():
        return None

    return storage_dir


def get_sessions_sorted(project_dir: Path) -> List[Path]:
    """Get all session files sorted by modification time (newest first)."""
    sessions = list(project_dir.glob('*.jsonl'))
    main_sessions = [s for s in sessions if not s.name.startswith('agent-')]
    return sorted(main_sessions, key=lambda p: p.stat().st_mtime, reverse=True)


def get_sessions_sorted_opencode(storage_dir: Path) -> List[Path]:
    """
    Get all OpenCode session files sorted by modification time.
    OpenCode stores sessions at: storage/session/{projectHash}/{sessionID}.json
    """
    session_dir = storage_dir / 'session'
    if not session_dir.exists():
        return []

    sessions = []
    for project_hash_dir in session_dir.iterdir():
        if project_hash_dir.is_dir():
            for session_file in project_hash_dir.glob('*.json'):
                sessions.append(session_file)

    return sorted(sessions, key=lambda p: p.stat().st_mtime, reverse=True)


def get_session_first_timestamp(session_file: Path) -> Optional[str]:
    """Get the timestamp of the first message in a session."""
    try:
        with open(session_file, 'r') as f:
            for line in f:
                try:
                    data = json.loads(line)
                    ts = data.get('timestamp')
                    if ts:
                        return ts
                except:
                    continue
    except:
        pass
    return None


def scan_for_planning_update(session_file: Path) -> Tuple[int, Optional[str]]:
    """
    Quickly scan a session file for planning file updates.
    Returns (line_number, filename) of last update, or (-1, None) if none found.
    """
    last_update_line = -1
    last_update_file = None

    try:
        with open(session_file, 'r') as f:
            for line_num, line in enumerate(f):
                if '"Write"' not in line and '"Edit"' not in line:
                    continue

                try:
                    data = json.loads(line)
                    if data.get('type') != 'assistant':
                        continue

                    content = data.get('message', {}).get('content', [])
                    if not isinstance(content, list):
                        continue

                    for item in content:
                        if item.get('type') != 'tool_use':
                            continue
                        tool_name = item.get('name', '')
                        if tool_name not in ('Write', 'Edit'):
                            continue

                        file_path = item.get('input', {}).get('file_path', '')
                        for pf in PLANNING_FILES:
                            if file_path.endswith(pf):
                                last_update_line = line_num
                                last_update_file = pf
                                break
                except json.JSONDecodeError:
                    continue
    except Exception:
        pass

    return last_update_line, last_update_file


def extract_messages_from_session(session_file: Path, after_line: int = -1) -> List[Dict]:
    """
    Extract conversation messages from a session file.
    If after_line >= 0, only extract messages after that line.
    If after_line < 0, extract all messages.
    """
    result = []

    try:
        with open(session_file, 'r') as f:
            for line_num, line in enumerate(f):
                if after_line >= 0 and line_num <= after_line:
                    continue

                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
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
                        # Skip system/command messages
                        if content.startswith(('<local-command', '<command-', '<task-notification')):
                            continue
                        if len(content) > 20:
                            result.append({
                                'role': 'user',
                                'content': content,
                                'line': line_num,
                                'session': session_file.stem[:8]
                            })

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
                                elif tool_name == 'AskUserQuestion':
                                    tool_uses.append("AskUserQuestion")
                                else:
                                    tool_uses.append(f"{tool_name}")

                    if text_content or tool_uses:
                        result.append({
                            'role': 'assistant',
                            'content': text_content[:600] if text_content else '',
                            'tools': tool_uses,
                            'line': line_num,
                            'session': session_file.stem[:8]
                        })
    except Exception:
        pass

    return result


def main():
    project_path = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()

    # Detect IDE
    ide = detect_ide()

    if ide == 'opencode':
        print("\n[planning-with-files] OpenCode session catchup is not yet fully supported")
        print("OpenCode uses a different session storage format (.json) than Claude Code (.jsonl)")
        print("Session catchup requires parsing OpenCode's message storage structure.")
        print("\nWorkaround: Manually read task_plan.md, progress.md, and findings.md to catch up.")
        return

    # Claude Code path
    project_dir = get_project_dir_claude(project_path)

    if not project_dir.exists():
        return

    sessions = get_sessions_sorted(project_dir)
    if len(sessions) < 2:
        return

    # Skip the current session (most recently modified = index 0)
    previous_sessions = sessions[1:]

    # Find the most recent planning file update across ALL previous sessions
    # Sessions are sorted newest first, so we scan in order
    update_session = None
    update_line = -1
    update_file = None
    update_session_idx = -1

    for idx, session in enumerate(previous_sessions):
        line, filename = scan_for_planning_update(session)
        if line >= 0:
            update_session = session
            update_line = line
            update_file = filename
            update_session_idx = idx
            break

    if not update_session:
        # No planning file updates found in any previous session
        return

    # Collect ALL messages from the update point forward, across all sessions
    all_messages = []

    # 1. Get messages from the session with the update (after the update line)
    messages_from_update_session = extract_messages_from_session(update_session, after_line=update_line)
    all_messages.extend(messages_from_update_session)

    # 2. Get ALL messages from sessions between update_session and current
    # These are sessions[1:update_session_idx] (newer than update_session)
    intermediate_sessions = previous_sessions[:update_session_idx]

    # Process from oldest to newest for correct chronological order
    for session in reversed(intermediate_sessions):
        messages = extract_messages_from_session(session, after_line=-1)  # Get all messages
        all_messages.extend(messages)

    if not all_messages:
        return

    # Output catchup report
    print(f"\n[planning-with-files] SESSION CATCHUP DETECTED (IDE: {ide})")
    print(f"Last planning update: {update_file} in session {update_session.stem[:8]}...")

    sessions_covered = update_session_idx + 1
    if sessions_covered > 1:
        print(f"Scanning {sessions_covered} sessions for unsynced context")

    print(f"Unsynced messages: {len(all_messages)}")

    print("\n--- UNSYNCED CONTEXT ---")

    # Show up to 100 messages
    MAX_MESSAGES = 100
    if len(all_messages) > MAX_MESSAGES:
        print(f"(Showing last {MAX_MESSAGES} of {len(all_messages)} messages)\n")
        messages_to_show = all_messages[-MAX_MESSAGES:]
    else:
        messages_to_show = all_messages

    current_session = None
    for msg in messages_to_show:
        # Show session marker when it changes
        if msg.get('session') != current_session:
            current_session = msg.get('session')
            print(f"\n[Session: {current_session}...]")

        if msg['role'] == 'user':
            print(f"USER: {msg['content'][:300]}")
        else:
            if msg.get('content'):
                print(f"CLAUDE: {msg['content'][:300]}")
            if msg.get('tools'):
                print(f"  Tools: {', '.join(msg['tools'][:4])}")

    print("\n--- RECOMMENDED ---")
    print("1. Run: git diff --stat")
    print("2. Read: task_plan.md, progress.md, findings.md")
    print("3. Update planning files based on above context")
    print("4. Continue with task")


if __name__ == '__main__':
    main()
