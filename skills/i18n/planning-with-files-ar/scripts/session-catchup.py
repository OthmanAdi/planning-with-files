#!/usr/bin/env python3
"""
سكريبت استئناف الجلسة لـ planning-with-files-ar

يحلل الجلسة السابقة للعثور على سياق غير متزامن بعد آخر
تحديث لملف التخطيط. مصمم للعمل عند بداية الجلسة.

الاستخدام: python3 session-catchup.py [مسار-المشروع]
"""

import json
import re
import sys
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


def configure_utf8_stdio() -> None:
    """Make catchup output deterministic on Windows legacy code pages.

    Codex sessions and planning files are UTF-8 and can contain arbitrary
    Unicode. Windows PowerShell may nevertheless launch Python with a cp1252
    (or another OEM/ANSI) stdout codec. A report containing Chinese text then
    used to fail at the first ``print`` with ``UnicodeEncodeError``. Configure
    both streams before any report is emitted; ``errors='replace'`` also keeps
    this advisory hook fail-safe if a malformed surrogate reaches the output.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, 'reconfigure', None)
        if callable(reconfigure):
            try:
                reconfigure(encoding='utf-8', errors='replace')
            except (OSError, ValueError):
                # Replaced/captured streams may not permit reconfiguration.
                # The hook remains advisory, so retain the existing stream.
                pass


configure_utf8_stdio()

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


def _claude_sanitize(path_str: str, astral_width: int = 2) -> str:
    """Claude Code's project-dir name for a project path.

    Every character outside [A-Za-z0-9_-] becomes '-', and the leading dash of
    POSIX absolute paths is kept (real stores look like -home-user-proj). The
    count is in UTF-16 code units rather than codepoints, so a non-BMP
    character such as an emoji in a folder name costs TWO dashes; passing
    astral_width=1 produces the codepoint-width spelling for older stores.

    Underscores are NOT universally kept: current versions fold '_' to '-'
    while older stores kept it, and both spellings are live on disk, so
    get_claude_project_dir() probes both.
    """
    return re.sub(
        r'[^A-Za-z0-9_-]',
        lambda m: '-' * (astral_width if ord(m.group()) > 0xFFFF else 1),
        path_str,
    )


def _newest_session_cwd_matches(project_dir: Path, normalized: str) -> bool:
    """True when a recent session in project_dir records normalized as its cwd."""
    for session in get_sessions_sorted(project_dir)[:3]:
        try:
            with open(session, 'r', encoding='utf-8', errors='replace') as f:
                for _ in range(50):
                    line = f.readline()
                    if not line:
                        break
                    match = re.search(r'"cwd"\s*:\s*"((?:[^"\\]|\\.)*)"', line)
                    if not match:
                        continue
                    try:
                        cwd = json.loads('"' + match.group(1) + '"')
                    except ValueError:
                        cwd = match.group(1)
                    a = cwd.replace('\\', '/').rstrip('/')
                    b = normalized.replace('\\', '/').rstrip('/')
                    if os.name == 'nt':
                        a, b = a.lower(), b.lower()
                    return a == b
        except OSError:
            continue
    return False


def get_claude_project_dir(project_path: str) -> Path:
    """Resolve Claude Code's project-specific session storage path.

    Claude Code keeps underscores and the leading dash of POSIX absolute
    paths when it names ~/.claude/projects/ entries. Earlier versions of
    this script guessed a single name with '_' replaced by '-' and the
    leading dash stripped, which silently missed the real store on every
    macOS/Linux install and on any project path containing an underscore.
    The legacy spellings are still probed so stores created under them keep
    working, and ambiguity is settled by the cwd recorded in the newest
    session file.
    """
    normalized = normalize_path(project_path)
    projects_root = Path.home() / '.claude' / 'projects'

    primary = _claude_sanitize(normalized)
    candidates = [primary]
    for width in (2, 1):
        exact = _claude_sanitize(normalized, width)
        for spelling in (exact, exact.replace('_', '-')):
            if spelling not in candidates:
                candidates.append(spelling)
    for cand in list(candidates):
        stripped = cand[1:] if cand.startswith('-') else cand
        if stripped and stripped not in candidates:
            candidates.append(stripped)

    existing = [projects_root / c for c in candidates
                if (projects_root / c).is_dir()]
    if not existing:
        return projects_root / primary
    if len(existing) == 1:
        return existing[0]
    for directory in existing:
        if _newest_session_cwd_matches(directory, normalized):
            return directory
    return existing[0]


def get_sessions_sorted(project_dir: Path) -> List[Path]:
    """Get all session files sorted by modification time (newest first)."""
    sessions = list(project_dir.glob('*.jsonl'))
    main_sessions = [s for s in sessions if not s.name.startswith('agent-')]
    return sorted(main_sessions, key=safe_stat_mtime, reverse=True)


def claude_session_cwd(session_file: Path) -> Optional[str]:
    """The cwd a Claude Code transcript records, or None if it records none."""
    try:
        with open(session_file, 'r', encoding='utf-8', errors='replace') as f:
            for _ in range(50):
                line = f.readline()
                if not line:
                    break
                data = json_loads(line)
                if data:
                    cwd = data.get('cwd')
                    if isinstance(cwd, str) and cwd:
                        return cwd
    except OSError:
        return None
    return None


def same_project_path(left: str, right: str) -> bool:
    """Compare two absolute paths the way the host filesystem would."""
    a, b = normalize_for_compare(left), normalize_for_compare(right)
    if os.name == 'nt':
        a, b = a.lower(), b.lower()
    return a == b


def filter_sessions_by_cwd(sessions: List[Path], project_path: str) -> Tuple[List[Path], Optional[str]]:
    """Drop transcripts that positively belong to a different project.

    Claude Code folds project paths into a single directory name, so two
    projects whose paths differ only in folded characters (client.acme and
    client-acme both fold to client-acme) share one store. Without this
    filter a catchup in one of them prints the other's conversation into the
    fresh context.

    Fail open: transcripts that record no cwd are kept, because that field is
    not present in every generation of the format, and a store whose sessions
    all record another project is reported rather than silently used.
    Returns (sessions_to_use, notice).
    """
    project_cmp = normalize_path(project_path)
    mine: List[Path] = []
    unknown: List[Path] = []
    foreign: List[str] = []
    for session in sessions:
        cwd = claude_session_cwd(session)
        if cwd is None:
            unknown.append(session)
        elif same_project_path(cwd, project_cmp):
            mine.append(session)
        else:
            foreign.append(cwd)

    if mine:
        keep = [s for s in sessions if s in mine or s in unknown]
        return keep, None
    if foreign:
        return [], (
            "[planning-with-files] Session catchup skipped: "
            f"{Path(sorted(set(foreign))[0]).name} and this project share one "
            "~/.claude/projects directory, so no transcript here belongs to "
            f"{project_cmp}."
        )
    return unknown, None


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
    if '/.codex/' in Path(__file__).resolve().as_posix().lower():
        return 'codex', get_codex_sessions(project_path)

    claude_project_dir = get_claude_project_dir(project_path)
    if claude_project_dir.exists():
        sessions, notice = filter_sessions_by_cwd(
            get_sessions_sorted(claude_project_dir), project_path
        )
        if notice:
            print(notice)
        return 'claude', sessions
    return 'claude', []


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
    print("\n[planning-with-files-ar] تم اكتشاف جلسة سابقة غير متزامنة")
    print(f"الجلسة السابقة: {target_session.stem}")
    print(f"بيئة التشغيل: {runtime_name}")

    print(f"آخر تحديث للتخطيط: {last_update_file} at message #{last_update_line}")
    print(f"الرسائل غير المتزامنة: {len(messages_after)}")

    print("\n--- سياق غير متزامن ---")
    assistant_label = 'CODEX' if runtime_name == 'codex' else 'CLAUDE'
    for msg in messages_after[-15:]:  # Last 15 messages
        if msg['role'] == 'user':
            print(f"المستخدم: {msg['content'][:300]}")
        else:
            if msg.get('content'):
                print(f"{assistant_label}: {msg['content'][:300]}")
            if msg.get('tools'):
                print(f"  الأدوات: {', '.join(msg['tools'][:4])}")

    print("\n--- التوصيات ---")
    print("1. نفّذ: git diff --stat")
    print("2. اقرأ: task_plan.md و progress.md و findings.md")
    print("3. حدّث ملفات التخطيط بناءً على السياق أعلاه")
    print("4. تابع المهمة")


if __name__ == '__main__':
    main()
