#!/usr/bin/env python3
from __future__ import annotations

import codex_hook_adapter as adapter


def main() -> None:
    payload = adapter.load_payload()
    root = adapter.cwd_from_payload(payload)

    if not adapter.is_session_attached(root, adapter.session_id_from_payload(payload)):
        adapter.emit_json({"decision": "allow"})
        return

    stdout, stderr = adapter.run_shell_script("pre-tool-use.sh", root)

    result = adapter.parse_json(stdout)
    decision = result.get("decision")
    if decision and decision != "allow":
        adapter.emit_json(result)
        return

    if stderr:
        adapter.emit_json({"systemMessage": stderr})


if __name__ == "__main__":
    raise SystemExit(adapter.main_guard(main))
