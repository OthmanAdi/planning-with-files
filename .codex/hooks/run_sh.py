#!/usr/bin/env python3
"""planning-with-files: Windows front-door for the pure-shell Codex hooks.

The three shell-only hooks (session-start, user-prompt-submit, pre-compact) are
invoked directly as ``sh <script>.sh`` on macOS/Linux. On Windows their
``commandWindows`` routes here:

    cmd /c .codex\\hooks\\pwf-hook.cmd run_sh.py session-start.sh

We reuse the adapter's shell resolver, which locates the git-for-windows
``sh.exe`` and puts its coreutils on PATH, then run the same ``.sh`` the unix
hook runs. Codex requires SessionStart and UserPromptSubmit command hooks to
return event-specific JSON, so shell stdout is wrapped before it is emitted.
Never used on unix. Always exits 0.
"""
from __future__ import annotations

import sys

import codex_hook_adapter as adapter


CONTEXT_EVENTS = {
    "session-start.sh": "SessionStart",
    "user-prompt-submit.sh": "UserPromptSubmit",
}


def main() -> None:
    if len(sys.argv) < 2:
        return
    script_name = sys.argv[1]
    payload = adapter.load_payload()
    root = adapter.cwd_from_payload(payload)
    stdout, _ = adapter.run_shell_script(script_name, root)
    event_name = CONTEXT_EVENTS.get(script_name)
    if stdout and event_name:
        adapter.emit_json(
            {
                "continue": True,
                "hookSpecificOutput": {
                    "hookEventName": event_name,
                    "additionalContext": stdout,
                },
            }
        )
    elif stdout and script_name == "pre-compact.sh":
        adapter.emit_json({"continue": True, "systemMessage": stdout})


if __name__ == "__main__":
    raise SystemExit(adapter.main_guard(main))
