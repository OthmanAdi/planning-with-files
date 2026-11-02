#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any


HOOK_DIR = Path(__file__).resolve().parent
_SAFE_LEGACY_SESSION_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_PLAN_SLUG = re.compile(r"[A-Za-z0-9_][A-Za-z0-9._-]*\Z")
SESSION_PLAN_BINDING_NOTICE = (
    "[planning-with-files] Multiple plans are available. "
    "Set PLAN_ID=<slug> for this session; nothing injected. "
    "Finished plans can be archived with set-active-plan --archive <slug>."
)
_DARWIN_SYSTEM_ALIASES = {
    Path("/var"): Path("/private/var"),
    Path("/tmp"): Path("/private/tmp"),
    Path("/etc"): Path("/private/etc"),
}


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


def canonical_project(root: Path) -> Path | None:
    try:
        return root.resolve(strict=True)
    except (OSError, RuntimeError):
        return None


def canonical_project_identity(root: Path) -> str | None:
    """Stable project spelling shared with direct shell session fallback."""
    project = canonical_project(root)
    if project is None:
        return None
    return os.path.normcase(os.path.realpath(os.path.abspath(project))).replace("\\", "/")


def state_key(host: str, root: Path, session_id: str) -> str | None:
    """Opaque, fixed-width key scoped by host, project, and native session."""
    project = canonical_project_identity(root)
    if project is None or not session_id:
        return None
    digest = hashlib.sha256()
    for value in (host, project, session_id):
        encoded = value.encode("utf-8", errors="surrogatepass")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return digest.hexdigest()


def _is_reparse_or_link(path: Path) -> bool:
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode):
        return True
    attrs = getattr(info, "st_file_attributes", 0)
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attrs & reparse)


_LINK_REPARSE_TAGS = (0xA000000C, 0xA0000003)  # IO_REPARSE_TAG_SYMLINK, _MOUNT_POINT


def _is_linked_directory(path: Path) -> bool:
    """`[ -L ]` of the shell scripts: a symlink, or a junction on Windows.

    Narrower than _is_reparse_or_link on purpose: OneDrive Files On-Demand
    marks every synced directory as a reparse point, and those are plans.
    """
    try:
        info = path.lstat()
    except OSError:
        return False
    if stat.S_ISLNK(info.st_mode):
        return True
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    if getattr(info, "st_file_attributes", 0) & reparse:
        return getattr(info, "st_reparse_tag", 0) in _LINK_REPARSE_TAGS
    return False


def _is_trusted_darwin_system_alias(path: Path) -> bool:
    """Admit only macOS's fixed root aliases after verifying their targets."""
    if sys.platform != "darwin":
        return False
    absolute = Path(os.path.abspath(path))
    expected = _DARWIN_SYSTEM_ALIASES.get(absolute)
    if expected is None:
        return False
    try:
        info = absolute.lstat()
        if not stat.S_ISLNK(info.st_mode):
            return False
        link_target = Path(os.readlink(absolute))
        if not link_target.is_absolute():
            link_target = absolute.parent / link_target
        if Path(os.path.normpath(link_target)) != expected:
            return False
        if Path(os.path.realpath(absolute)) != expected:
            return False
        target_info = expected.lstat()
    except (OSError, RuntimeError):
        return False
    return stat.S_ISDIR(target_info.st_mode) and not _is_reparse_or_link(expected)


def _has_reparse_component(path: Path) -> bool:
    absolute = Path(os.path.abspath(path))
    current = Path(absolute.anchor)
    try:
        for part in absolute.parts[1:]:
            current /= part
            if _is_reparse_or_link(current) and not _is_trusted_darwin_system_alias(
                current
            ):
                return True
    except (OSError, RuntimeError):
        return True
    return False


def effective_plan_root(cwd: Path) -> Path | None:
    """Resolve the plan root the hooks must read planning state from.

    Issue #212: PWF_PLAN_ROOT pins a thread whose cwd is a shared parent of
    the real project (e.g. /workspace above /workspace/project) to the project
    root that owns the plan. Highest precedence. Every entrypoint routes its
    shell helper and session-attachment check through the returned root, so
    all planning-state reads go through the pin.

    A pin that is not a directory fails CLOSED (returns None): the hooks
    inject nothing rather than silently falling back to the ambiguous cwd
    plan the pin was escaping. The user-facing notice for a broken pin lives
    in user-prompt-submit.sh, the once-per-turn hook; the per-tool-call hooks
    served by this adapter must refuse silently or the notice becomes spam.

    With the variable unset the cwd passes through untouched (legacy
    invariant).
    """
    pin = os.environ.get("PWF_PLAN_ROOT", "")
    if not pin:
        return cwd
    pin_path = Path(pin)
    if not pin_path.is_absolute() or str(pin_path).startswith(("\\\\", "//")):
        return None
    try:
        cwd_real = cwd.resolve(strict=True)
        pin_real = pin_path.resolve(strict=True)
        if _has_reparse_component(pin_path) or not pin_real.is_dir():
            return None
        pin_real.relative_to(cwd_real)
    except (OSError, RuntimeError, ValueError):
        return None
    return pin_real


def is_session_attached(root: Path, session_id: str | None) -> bool:
    """Return True if this session should receive plan context.

    Legacy mode: if .planning/sessions/ does not exist, always return True so
    existing single-session users are not broken on upgrade.
    Isolation mode: return True only when the session has an attached sentinel.
    """
    if os.environ.get("PLANNING_DISABLED", "") == "1":
        return False  # issue #195: explicit per-invocation opt-out (one-shot exec/CI)
    sessions_dir = root / ".planning" / "sessions"
    try:
        sessions_info = sessions_dir.lstat()
    except FileNotFoundError:
        return True  # legacy — no sessions dir means single-session setup
    except OSError:
        return False
    if not session_id:
        return False  # sessions dir exists but caller has no ID — stay silent
    try:
        project = canonical_project(root)
        if (
            project is None
            or _is_reparse_or_link(sessions_dir)
            or not stat.S_ISDIR(sessions_info.st_mode)
        ):
            return False
        sessions_real = sessions_dir.resolve(strict=True)
        sessions_real.relative_to(project)
        key = state_key("codex", project, session_id)
        if key is None:
            return False
        candidates = [sessions_real / f"{key}.attached"]
        if _SAFE_LEGACY_SESSION_ID.fullmatch(session_id):
            candidates.append(sessions_real / f"{session_id}.attached")
        for sentinel in candidates:
            try:
                sentinel_info = sentinel.lstat()
                if _is_reparse_or_link(sentinel) or not stat.S_ISREG(sentinel_info.st_mode):
                    continue
                sentinel.resolve(strict=True).relative_to(sessions_real)
                current = sentinel.stat()
                if (
                    stat.S_ISREG(current.st_mode)
                    and (current.st_dev, current.st_ino)
                    == (sentinel_info.st_dev, sentinel_info.st_ino)
                ):
                    return True
            except (FileNotFoundError, OSError, RuntimeError, ValueError):
                continue
        return False
    except (OSError, RuntimeError, ValueError):
        return False


def session_plan_requires_binding(root: Path) -> bool:
    """Require PLAN_ID when an attached session can resolve multiple plans.

    Session sentinels admit a session to planning context. They do not select a
    plan. Multiple named plans always require a pin. With isolation armed,
    a legacy root plan also counts as a competing candidate.
    """
    if os.environ.get("PLAN_ID", ""):
        return False

    sessions_dir = root / ".planning" / "sessions"
    armed = sessions_dir.exists() or sessions_dir.is_symlink()
    planning_dir = root / ".planning"
    if not planning_dir.exists():
        return False

    candidates = 0
    try:
        if armed and (root / "task_plan.md").is_file():
            candidates += 1
        planning_dir = root / ".planning"
        for child in planning_dir.iterdir():
            if not _PLAN_SLUG.fullmatch(child.name) or not child.is_dir():
                continue
            # A linked plan directory is not selectable and never counts,
            # matching `[ -L ]` in the shell counters (#270).
            if _is_linked_directory(child):
                continue
            if (child / "task_plan.md").is_file():
                candidates += 1
                if candidates > 1:
                    return True
    except (OSError, RuntimeError):
        return True
    return False


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
    system32 = (Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32").resolve()
    for exe in ("sh", "bash"):
        found = shutil.which(exe)
        if found:
            candidate = Path(found).resolve()
            parent = candidate.parent
            # Windows' bash.exe is a WSL launcher, not a POSIX shell. Selecting
            # it before Git Bash makes every shell hook fail when WSL has no
            # installed distro (the common Git-for-Windows-only setup), and even
            # a working WSL bash cannot run C:\ script paths. The Store alias
            # under WindowsApps is the same launcher.
            if parent != system32 and parent.name.lower() != "windowsapps":
                return str(candidate), [str(parent)]

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


def run_shell_script(
    script_name: str,
    cwd: Path,
    *args: str,
    session_id: str | None = None,
) -> tuple[str, str]:
    sh_cmd = "sh"
    env = os.environ.copy()
    env["PWF_TRUSTED_PYTHON"] = str(Path(sys.executable).resolve())
    if session_id:
        # Native event JSON wins. Ambient PWF_SESSION_ID remains a fallback
        # only when the caller passed no native session.
        env["PWF_SESSION_ID"] = session_id
        key = state_key("codex", cwd, session_id)
        if key:
            env["PWF_SESSION_KEY"] = key
    if os.environ.get("PWF_PLAN_ROOT"):
        env["PWF_PLAN_ROOT"] = str(cwd)
    if os.name == "nt":
        sh_path, extra_dirs = _windows_git_bash()
        if sh_path is None:
            # No git bash reachable: run nothing rather than crash. An advisory
            # hook must never surface an error (issue #201). docs/codex.md tells
            # Windows users to install Git for Windows to enable these hooks.
            return "", ""
        sh_cmd = sh_path
        if extra_dirs:
            env["PATH"] = os.pathsep.join(extra_dirs) + os.pathsep + env.get("PATH", "")
        # session-catchup.py resolves via $PYTHON_BIN first; hand it the real
        # interpreter so it never falls back to the Store python3.exe stub.
        env["PYTHON_BIN"] = sys.executable

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
