#!/usr/bin/env python3
"""Run local planning producers and translate their Stop decision to Qoder CLI.

The shared Codex producer uses decision=block with exit zero. Qoder CLI's
documented blocking contract is exit two with the reason on stderr. Keep this
translation out of the shared producer so other hosts retain their protocol.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROUTES = {
    "SessionStart": ("run_sh.py", "session-start.sh"),
    "UserPromptSubmit": ("run_sh.py", "user-prompt-submit.sh"),
    "PreToolUse": ("pre_tool_use.py",),
    "PermissionRequest": ("permission_request.py",),
    "PostToolUse": ("post_tool_use.py",),
    "PreCompact": ("run_sh.py", "pre-compact.sh"),
    "Stop": ("stop.py",),
}


def main() -> int:
    raw = sys.stdin.buffer.read()
    try:
        payload = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return 0
    if not isinstance(payload, dict):
        return 0
    event = payload.get("hook_event_name")
    if not isinstance(event, str) or event not in ROUTES:
        return 0
    route = ROUTES[event]
    hooks = Path(__file__).resolve().parents[1] / ".codex" / "hooks"
    result = subprocess.run(
        [
            sys.executable, "-I", "-c",
            "import runpy,sys; from pathlib import Path; "
            "sys.path.insert(0,str(Path(sys.argv[1]).resolve().parent)); "
            "sys.argv=sys.argv[1:]; runpy.run_path(sys.argv[0],run_name='__main__')",
            str(hooks / route[0]), *route[1:],
        ],
        input=raw, capture_output=True, check=False,
    )
    if event == "Stop" and result.returncode == 0:
        try:
            output = json.loads(result.stdout)
        except (UnicodeDecodeError, json.JSONDecodeError):
            output = None
        if isinstance(output, dict) and output.get("decision") == "block":
            reason = output.get("reason")
            if payload.get("stop_hook_active") is not True and isinstance(reason, str) and reason:
                sys.stderr.write(reason + "\n")
                return 2
            return 0
    sys.stdout.buffer.write(result.stdout)
    sys.stderr.buffer.write(result.stderr)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
