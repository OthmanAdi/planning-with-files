#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


HOOK_DIR = Path(__file__).resolve().parent


def load_payload() -> dict[str, Any]:
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def cwd_from_payload(payload: dict[str, Any]) -> Path:
    cwd = payload.get("cwd")
    if isinstance(cwd, str) and cwd:
        return Path(cwd)
    return Path.cwd()


def session_id_from_payload(payload: dict[str, Any]) -> str | None:
    sid = payload.get("session_id")
    if isinstance(sid, str) and sid:
        return sid
    env_sid = os.environ.get("PWF_SESSION_ID", "")
    return env_sid if env_sid else None


def is_session_attached(root: Path, session_id: str | None) -> bool:
    """Return True if this session should receive plan context.

    Legacy mode: if .planning/sessions/ does not exist, always return True so
    existing single-session users are not broken on upgrade.
    Isolation mode: return True only when the session has an attached sentinel.
    """
    if os.environ.get("PLANNING_DISABLED", "") == "1":
        return False  # issue #195: explicit per-invocation opt-out (one-shot exec/CI)
    sessions_dir = root / ".planning" / "sessions"
    if not sessions_dir.exists():
        return True  # legacy — no sessions dir means single-session setup
    if not session_id:
        return False  # sessions dir exists but caller has no ID — stay silent
    return (sessions_dir / f"{session_id}.attached").exists()


def emit_json(payload: dict[str, Any]) -> None:
    if not payload:
        return
    json.dump(payload, sys.stdout, ensure_ascii=True)
    sys.stdout.write("\n")


def parse_json(text: str) -> dict[str, Any]:
    if not text.strip():
        return {}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _windows_git_bash() -> tuple[str | None, list[str]]:
    """Locate git-for-windows sh.exe plus the unix-tools dirs the .sh hooks need.

    Returns (sh_path, extra_path_dirs). A default Git-for-Windows install puts
    only cmd\\git.exe on PATH, not usr\\bin\\sh.exe or the coreutils (grep, head,
    date, tr) the hook scripts call and re-invoke via nested `sh`. So when `sh`
    is not directly on PATH we anchor on git.exe (or the standard install roots)
    and probe for sh.exe and its sibling bin dirs. This is exactly issue #201:
    the reporter had git bash installed but its usr\\bin was not on PATH.
    """
    for exe in ("sh", "bash"):
        found = shutil.which(exe)
        if found:
            return found, [str(Path(found).parent)]

    roots: list[Path] = []
    git = shutil.which("git")
    if git:
        # <root>\cmd\git.exe or <root>\bin\git.exe -> <root>
        roots.append(Path(git).resolve().parent.parent)
    for env_var in ("ProgramW6432", "ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        base = os.environ.get(env_var)
        if base:
            roots.append(Path(base) / "Git")
            roots.append(Path(base) / "Programs" / "Git")

    for root in roots:
        sh_exe = root / "usr" / "bin" / "sh.exe"
        if sh_exe.exists():
            extra = [root / "usr" / "bin", root / "bin", root / "mingw64" / "bin"]
            return str(sh_exe), [str(d) for d in extra if d.exists()]
    return None, []


def run_shell_script(script_name: str, cwd: Path, *args: str) -> tuple[str, str]:
    sh_cmd = "sh"
    env = None
    if os.name == "nt":
        sh_path, extra_dirs = _windows_git_bash()
        if sh_path is None:
            # No git bash reachable: run nothing rather than crash. An advisory
            # hook must never surface an error (issue #201). docs/codex.md tells
            # Windows users to install Git for Windows to enable these hooks.
            return "", ""
        sh_cmd = sh_path
        env = os.environ.copy()
        if extra_dirs:
            env["PATH"] = os.pathsep.join(extra_dirs) + os.pathsep + env.get("PATH", "")
        # session-catchup.py resolves via $PYTHON_BIN first; hand it the real
        # interpreter so it never falls back to the Store python3.exe stub.
        env.setdefault("PYTHON_BIN", sys.executable)

    result = subprocess.run(
        [sh_cmd, str(HOOK_DIR / script_name), *args],
        cwd=str(cwd),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
        env=env,
    )
    return result.stdout.strip(), result.stderr.strip()


def main_guard(func) -> int:
    try:
        func()
    except Exception as exc:  # pragma: no cover
        print(f"[planning-with-files hook] {exc}", file=sys.stderr)
        return 0
    return 0

