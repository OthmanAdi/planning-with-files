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
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    import orjson
except ImportError:
    orjson = None

PLANNING_FILES = ['task_plan.md', 'progress.md', 'findings.md']
MIN_SESSION_BYTES = 5000


def json_loads(line: str) -> Optional[Dict[str, Any]]:
    """Prefer optional orjson while keeping the hook dependency-free."""
    try:
        if orjson is not None:
            data = orjson.loads(line)
        else:
            data = json.loads(line)
    except (ValueError, TypeError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None


def normalize_for_compare(path_value: str) -> str:
    expanded = os.path.expanduser(path_value)
    try:
        return str(Path(expanded).resolve())
    except (OSError, ValueError):
        return os.path.abspath(expanded)


def normalize_path(project_path: str) -> str:
    """Normalize project path to match Claude Code's internal representation.

    Claude Code stores session directories using the Windows-native path
    (e.g., C:\\Users\\...) sanitized with separators replaced by dashes.
    Git Bash passes /c/Users/... which produces a DIFFERENT sanitized
    string. This function converts Git Bash paths to Windows paths first.
    """
    p = project_path

    # Git Bash / MSYS2: /c/Users/... -> C:/Users/...
    if len(p) >= 3 and p[0] == '/' and p[2] == '/':
        p = p[1].upper() + ':' + p[2:]

    # Resolve to absolute path to handle relative paths and symlinks
    try:
        resolved = str(Path(p).resolve())
        # On Windows, resolve() returns C:\Users\... which is what we want
        if os.name == 'nt' or '\\' in resolved:
            p = resolved
    except (OSError, ValueError):
        pass

    return p


def get_claude_project_dir(project_path: str) -> Path:
    """Resolve Claude Code's project-specific session storage path."""
    normalized = normalize_path(project_path)

    # Claude Code's sanitization: replace path separators and : with -
    sanitized = normalized.replace('\\', '-').replace('/', '-').replace(':', '-')
    sanitized = sanitized.replace('_', '-')
    # Strip leading dash if present (Unix absolute paths start with /)
    if sanitized.startswith('-'):
        sanitized = sanitized[1:]

    return Path.home() / '.claude' / 'projects' / sanitized


def get_sessions_sorted(project_dir: Path) -> List[Path]:
    """Get all session files sorted by modification time (newest first)."""
    sessions = list(project_dir.glob('*.jsonl'))
    main_sessions = [s for s in sessions if not s.name.startswith('agent-')]
    return sorted(main_sessions, key=safe_stat_mtime, reverse=True)


def safe_stat_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def is_substantial_session(session: Path) -> bool:
    try:
        return session.stat().st_size > MIN_SESSION_BYTES
    except OSError:
        return False


def read_codex_meta(session_file: Path) -> Optional[Dict[str, Any]]:
    """Read the first session_meta; later meta records may be copied parent context."""
    try:
        with open(session_file, 'r', encoding='utf-8', errors='replace') as f:
            for line in f:
                data = json_loads(line)
                if not data or data.get('type') != 'session_meta':
                    continue
                payload = data.get('payload')
                return payload if isinstance(payload, dict) else None
    except OSError:
        return None
    return None


def codex_meta_cwd(meta: Dict[str, Any]) -> Optional[str]:
    cwd = meta.get('cwd')
    return cwd if isinstance(cwd, str) else None


def find_current_codex_session(sessions: List[Path]) -> Optional[Path]:
    thread_id = os.getenv('CODEX_THREAD_ID', '').strip()
    if not thread_id:
        return None

    for session in sessions:
        if thread_id in session.name:
            return session
    return None


def is_codex_project_session(session: Path, project_cmp: str) -> bool:
    if not is_substantial_session(session):
        return False

    meta = read_codex_meta(session)
    if not meta:
        return False
    source = meta.get('source')
    if isinstance(source, dict) and 'subagent' in source:
        return False
    cwd = codex_meta_cwd(meta)
    return bool(cwd and normalize_for_compare(cwd) == project_cmp)


def get_codex_sessions(project_path: str) -> Iterable[Path]:
    sessions_dir = Path(os.path.expanduser(os.getenv('CODEX_SESSIONS_DIR', '~/.codex/sessions')))
    if not sessions_dir.exists():
        return

    project_cmp = normalize_for_compare(project_path)
    sessions = sorted(sessions_dir.rglob('rollout-*.jsonl'), key=safe_stat_mtime, reverse=True)
    current = find_current_codex_session(sessions)
    if current and is_codex_project_session(current, project_cmp):
        yield current

    for session in sessions:
        if session == current:
            continue
        if is_codex_project_session(session, project_cmp):
            yield session


def get_session_candidates(project_path: str) -> Tuple[str, Iterable[Path]]:
    script_path = Path(__file__).resolve().as_posix().lower()
    if '/.codex/' in script_path:
        return 'codex', get_codex_sessions(project_path)
    if '/.opencode/' in script_path:
        # OpenCode dispatch is handled separately via SQLite (v2.38.0+).
        return 'opencode', []

    claude_project_dir = get_claude_project_dir(project_path)
    if claude_project_dir.exists():
        return 'claude', get_sessions_sorted(claude_project_dir)
    return 'claude', []


PLANNING_LIKE_SQL = ('%task_plan.md', '%findings.md', '%progress.md')


def get_opencode_db_path() -> Optional[Path]:
    """Resolve OpenCode SQLite path. Same on all OS per xdg-basedir."""
    xdg = os.environ.get('XDG_DATA_HOME')
    if xdg:
        base = Path(xdg) / 'opencode'
    elif os.environ.get('OPENCODE_DATA_DIR'):
        base = Path(os.environ['OPENCODE_DATA_DIR'])
    else:
        base = Path.home() / '.local' / 'share' / 'opencode'
    db = base / 'opencode.db'
    return db if db.exists() else None


def _format_opencode_part(data: Dict[str, Any], session_id: str) -> Optional[Dict[str, Any]]:
    """Print-ready summary for one OpenCode part row."""
    ptype = data.get('type')
    short = session_id[:8] if session_id else '????????'
    if ptype == 'tool':
        tool = (data.get('tool') or '').lower()
        state = data.get('state') or {}
        input_ = state.get('input') or {}
        if tool in ('write', 'edit'):
            fp = input_.get('filePath', '')
            return {'session': short, 'summary': f"Tool {tool}: {fp}"}
        if tool == 'patch':
            return {'session': short, 'summary': f"Tool patch: {input_.get('filePath', '')}"}
        if tool == 'bash':
            cmd = (input_.get('command') or '')[:80]
            return {'session': short, 'summary': f"Tool bash: {cmd}"}
        return {'session': short, 'summary': f"Tool {tool}"}
    if ptype == 'text':
        text = (data.get('text') or '')[:300]
        if text.strip():
            return {'session': short, 'summary': f"text: {text}"}
    return None


def opencode_catchup(project_path: str) -> None:
    """Session catchup for OpenCode SQLite (v2.38.0+).

    Schema as of sst/opencode dev @ 2026-05-14:
      session (id, directory, time_created, ...)
      part    (id, session_id, message_id, time_created, data TEXT JSON)
    """
    import sqlite3

    db_path = get_opencode_db_path()
    if not db_path:
        return

    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.OperationalError:
        return

    cur = conn.cursor()
    try:
        cur.execute("PRAGMA table_info(session)")
        session_cols = {row[1] for row in cur.fetchall()}
        cur.execute("PRAGMA table_info(part)")
        part_cols = {row[1] for row in cur.fetchall()}
    except sqlite3.OperationalError:
        conn.close()
        return

    if 'directory' not in session_cols or 'data' not in part_cols:
        conn.close()
        return

    project_abs = normalize_for_compare(project_path)

    cur.execute(
        "SELECT id, time_created FROM session WHERE directory = ? ORDER BY time_created DESC",
        (project_abs,),
    )
    sessions = cur.fetchall()
    if len(sessions) < 2:
        conn.close()
        return

    previous_sessions = sessions[1:]

    update_sid = None
    update_time = None
    update_idx = -1
    for idx, (sid, _) in enumerate(previous_sessions):
        params = (sid,) + PLANNING_LIKE_SQL
        cur.execute(
            """
            SELECT time_created FROM part
            WHERE session_id = ?
              AND json_extract(data, '$.type') = 'tool'
              AND lower(json_extract(data, '$.tool')) IN ('write', 'edit', 'patch')
              AND (
                json_extract(data, '$.state.input.filePath') LIKE ?
                OR json_extract(data, '$.state.input.filePath') LIKE ?
                OR json_extract(data, '$.state.input.filePath') LIKE ?
              )
            ORDER BY time_created DESC
            LIMIT 1
            """,
            params,
        )
        row = cur.fetchone()
        if row:
            update_sid = sid
            update_time = row[0]
            update_idx = idx
            break

    if not update_sid:
        conn.close()
        return

    newer_sessions = list(reversed(previous_sessions[:update_idx]))

    parts: List[Dict[str, Any]] = []

    cur.execute(
        "SELECT data FROM part WHERE session_id = ? AND time_created > ? ORDER BY time_created ASC, id ASC",
        (update_sid, update_time),
    )
    for (data_str,) in cur.fetchall():
        try:
            data = json.loads(data_str)
        except json.JSONDecodeError:
            continue
        msg = _format_opencode_part(data, update_sid)
        if msg:
            parts.append(msg)

    for sid, _ in newer_sessions:
        cur.execute(
            "SELECT data FROM part WHERE session_id = ? ORDER BY time_created ASC, id ASC",
            (sid,),
        )
        for (data_str,) in cur.fetchall():
            try:
                data = json.loads(data_str)
            except json.JSONDecodeError:
                continue
            msg = _format_opencode_part(data, sid)
            if msg:
                parts.append(msg)

    conn.close()

    if not parts:
        return

    print(f"\n[planning-with-files] SESSION CATCHUP DETECTED (IDE: opencode)")
    print(f"Last planning update in session {update_sid[:8]}...")
    if update_idx + 1 > 1:
        print(f"Scanning {update_idx + 1} previous sessions for unsynced context")
    print(f"Unsynced parts: {len(parts)}")
    print("\n--- UNSYNCED CONTEXT ---")

    MAX_PARTS = 100
    if len(parts) > MAX_PARTS:
        print(f"(Showing last {MAX_PARTS} of {len(parts)} parts)\n")
        to_show = parts[-MAX_PARTS:]
    else:
        to_show = parts

    current_session = None
    for msg in to_show:
        if msg.get('session') != current_session:
            current_session = msg.get('session')
            print(f"\n[Session: {current_session}...]")
        print(f"  {msg['summary']}")

    print("\n--- RECOMMENDED ---")
    print("1. Run: git diff --stat")
    print("2. Read: task_plan.md, progress.md, findings.md")
    print("3. Update planning files based on above context")
    print("4. Continue with task")


def parse_session_messages(session_file: Path) -> List[Dict[str, Any]]:
    """Parse all messages from a session file, preserving order."""
    messages = []
    with open(session_file, 'r', encoding='utf-8', errors='replace') as f:
        for line_num, line in enumerate(f):
            data = json_loads(line)
            if data is not None:
                data['_line_num'] = line_num
                messages.append(data)
    return messages


def planning_file_from_path(path_value: Any) -> Optional[str]:
    if not isinstance(path_value, str):
        return None
    for pf in PLANNING_FILES:
        if path_value.endswith(pf):
            return pf
    return None


def planning_file_from_paths(paths: Iterable[Any]) -> Optional[str]:
    matches = {pf for path in paths if (pf := planning_file_from_path(path))}
    for pf in PLANNING_FILES:
        if pf in matches:
            return pf
    return None


def codex_planning_update(payload: Dict[str, Any]) -> Optional[str]:
    """Use Codex's structured apply_patch result instead of parsing tool text."""
    if payload.get('type') != 'patch_apply_end' or payload.get('success') is not True:
        return None
    changes = payload.get('changes')
    return planning_file_from_paths(changes.keys()) if isinstance(changes, dict) else None


def find_last_planning_update(messages: List[Dict[str, Any]]) -> Tuple[int, Optional[str]]:
    """
    Find the last time a planning file was written/edited.
    Returns (line_number, filename) or (-1, None) if not found.
    """
    last_update_line = -1
    last_update_file = None

    for msg in messages:
        line_num = msg.get('_line_num')
        if not isinstance(line_num, int):
            continue
        msg_type = msg.get('type')

        if msg_type == 'assistant':
            content = msg.get('message', {}).get('content', [])
            if isinstance(content, list):
                for item in content:
                    if item.get('type') == 'tool_use':
                        tool_name = item.get('name', '')
                        tool_input = item.get('input', {})
                        if not isinstance(tool_input, dict):
                            tool_input = {}

                        if tool_name in ('Write', 'Edit'):
                            planning_file = planning_file_from_path(tool_input.get('file_path', ''))
                            if planning_file:
                                last_update_line = line_num
                                last_update_file = planning_file

        elif msg_type == 'event_msg':
            payload = msg.get('payload')
            if isinstance(payload, dict):
                planning_file = codex_planning_update(payload)
                if planning_file:
                    last_update_line = line_num
                    last_update_file = planning_file

    return last_update_line, last_update_file


def text_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ''
    return '\n'.join(
        item.get('text', '')
        for item in content
        if isinstance(item, dict) and isinstance(item.get('text'), str)
    )


def parse_codex_tool_args(payload: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
    raw_args = payload.get('arguments', payload.get('input', ''))
    if isinstance(raw_args, dict):
        return raw_args, json.dumps(raw_args, ensure_ascii=True)
    if not isinstance(raw_args, str):
        return {}, ''
    decoded = json_loads(raw_args)
    return (decoded, raw_args) if isinstance(decoded, dict) else ({}, raw_args)


def summarize_codex_tool(payload: Dict[str, Any]) -> str:
    tool_name = payload.get('name', 'tool')
    tool_args, raw_args = parse_codex_tool_args(payload)
    if tool_name == 'exec_command':
        command = tool_args.get('cmd', raw_args)
        if isinstance(command, str):
            return f"exec_command: {command[:80]}"
    return str(tool_name)


def extract_messages_after(messages: List[Dict[str, Any]], after_line: int) -> List[Dict[str, Any]]:
    """Extract conversation messages after a certain line number."""
    result = []
    for msg in messages:
        line_num = msg.get('_line_num')
        if not isinstance(line_num, int) or line_num <= after_line:
            continue

        msg_type = msg.get('type')
        is_meta = msg.get('isMeta', False)

        if msg_type == 'user' and not is_meta:
            content = text_content(msg.get('message', {}).get('content', ''))

            if content:
                if content.startswith(('<local-command', '<command-', '<task-notification')):
                    continue
                if len(content) > 20:
                    result.append({'role': 'user', 'content': content, 'line': line_num})

        elif msg_type == 'assistant':
            msg_content = msg.get('message', {}).get('content', '')
            text = text_content(msg_content)
            tool_uses = []

            if isinstance(msg_content, list):
                for item in msg_content:
                    if isinstance(item, dict) and item.get('type') == 'tool_use':
                        tool_name = item.get('name', '')
                        tool_input = item.get('input', {})
                        if not isinstance(tool_input, dict):
                            tool_input = {}
                        if tool_name == 'Edit':
                            tool_uses.append(f"Edit: {tool_input.get('file_path', 'unknown')}")
                        elif tool_name == 'Write':
                            tool_uses.append(f"Write: {tool_input.get('file_path', 'unknown')}")
                        elif tool_name == 'Bash':
                            cmd = tool_input.get('command', '')[:80]
                            tool_uses.append(f"Bash: {cmd}")
                        else:
                            tool_uses.append(f"{tool_name}")

            if text or tool_uses:
                result.append({
                    'role': 'assistant',
                    'content': text[:600] if text else '',
                    'tools': tool_uses,
                    'line': line_num
                })

        elif msg_type == 'response_item':
            payload = msg.get('payload')
            if not isinstance(payload, dict):
                continue

            payload_type = payload.get('type')
            if payload_type == 'message':
                role = payload.get('role')
                if role not in ('user', 'assistant'):
                    continue
                content = text_content(payload.get('content'))
                if role == 'user':
                    if content.startswith(('<local-command', '<command-', '<task-notification')):
                        continue
                    if len(content) > 20:
                        result.append({'role': 'user', 'content': content, 'line': line_num})
                elif content:
                    result.append({
                        'role': 'assistant',
                        'content': content[:600],
                        'tools': [],
                        'line': line_num
                    })
            elif payload_type in ('function_call', 'custom_tool_call'):
                result.append({
                    'role': 'assistant',
                    'content': '',
                    'tools': [summarize_codex_tool(payload)],
                    'line': line_num
                })

    return result


def main():
    project_path = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()

    # Check if planning files exist (indicates active task)
    has_planning_files = any(
        Path(project_path, f).exists() for f in PLANNING_FILES
    )
    if not has_planning_files:
        # No planning files in this project; skip catchup to avoid noise.
        return

    runtime_name, sessions = get_session_candidates(project_path)

    if runtime_name == 'opencode':
        opencode_catchup(project_path)
        return

    # Find a substantial previous session
    target_session = None
    for session in sessions:
        if runtime_name == 'claude' and not is_substantial_session(session):
            continue
        target_session = session
        break

    if not target_session:
        return

    messages = parse_session_messages(target_session)
    last_update_line, last_update_file = find_last_planning_update(messages)

    # No planning updates in the target session; skip catchup output.
    if last_update_line < 0:
        return

    # Only output if there's unsynced content
    messages_after = extract_messages_after(messages, last_update_line)

    if not messages_after:
        return

    # Output catchup report
    print("\n[planning-with-files] SESSION CATCHUP DETECTED")
    print(f"Previous session: {target_session.stem}")
    print(f"Runtime: {runtime_name}")

    print(f"Last planning update: {last_update_file} at message #{last_update_line}")
    print(f"Unsynced messages: {len(messages_after)}")

    print("\n--- UNSYNCED CONTEXT ---")
    assistant_label = 'CODEX' if runtime_name == 'codex' else 'CLAUDE'
    for msg in messages_after[-15:]:  # Last 15 messages
        if msg['role'] == 'user':
            print(f"USER: {msg['content'][:300]}")
        else:
            if msg.get('content'):
                print(f"{assistant_label}: {msg['content'][:300]}")
            if msg.get('tools'):
                print(f"  Tools: {', '.join(msg['tools'][:4])}")

    print("\n--- RECOMMENDED ---")
    print("1. Run: git diff --stat")
    print("2. Read: task_plan.md, progress.md, findings.md")
    print("3. Update planning files based on above context")
    print("4. Continue with task")


if __name__ == '__main__':
    main()
