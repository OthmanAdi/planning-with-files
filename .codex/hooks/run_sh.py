#!/usr/bin/env python3
"""planning-with-files: Windows front-door for the pure-shell Codex hooks.

The three shell-only hooks (session-start, user-prompt-submit, pre-compact) are
invoked directly as ``sh <script>.sh`` on macOS/Linux. On Windows their
``commandWindows`` routes here:

    cmd /c .codex\\hooks\\pwf-hook.cmd run_sh.py session-start.sh

We reuse the adapter's shell resolver, which locates the git-for-windows
``sh.exe`` and puts its coreutils on PATH, then run the same ``.sh`` the unix
hook runs and print its stdout. Never used on unix. Always exits 0.
"""
from __future__ import annotations

import json
import sys

import codex_hook_adapter as adapter


def main() -> None:
    if len(sys.argv) < 2:
        return
    script_name = sys.argv[1]
    payload = adapter.load_payload()
    root = adapter.cwd_from_payload(payload)
    stdout, _ = adapter.run_shell_script(script_name, root)
    if not stdout:
        return

    context_events = {
        "session-start.sh": "SessionStart",
        "user-prompt-submit.sh": "UserPromptSubmit",
    }
    if script_name in context_events:
        result = {
            "hookSpecificOutput": {
                "hookEventName": context_events[script_name],
                "additionalContext": stdout,
            }
        }
        sys.stdout.write(json.dumps(result, ensure_ascii=True) + "\n")
        return

    if script_name == "pre-compact.sh":
        result = {
            "continue": True,
            "systemMessage": stdout,
        }
        sys.stdout.write(json.dumps(result, ensure_ascii=True) + "\n")
        return

    sys.stdout.write(stdout + "\n")


if __name__ == "__main__":
    raise SystemExit(adapter.main_guard(main))
