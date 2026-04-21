from __future__ import annotations

from typing import Dict, List

_SESSION_REMINDERS: Dict[str, List[str]] = {}


def add_reminder(session_id: str, message: str) -> None:
    if not session_id or not message:
        return
    bucket = _SESSION_REMINDERS.setdefault(session_id, [])
    if message not in bucket:
        bucket.append(message)


def pop_reminders(session_id: str) -> list[str]:
    if not session_id:
        return []
    return _SESSION_REMINDERS.pop(session_id, [])
