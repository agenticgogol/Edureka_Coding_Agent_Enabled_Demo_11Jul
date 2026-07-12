"""In-memory multi-turn session history, keyed by session_id.

Lost on server restart — acceptable for a live teaching demo, per the
approved teaching_brief.md decision.
"""
from __future__ import annotations

from threading import Lock

_sessions: dict[str, list[dict]] = {}
_lock = Lock()


def get_history(session_id: str) -> list[dict]:
    with _lock:
        return list(_sessions.get(session_id, []))


def append_turn(session_id: str, role: str, content: str) -> None:
    with _lock:
        _sessions.setdefault(session_id, []).append({"role": role, "content": content})


def clear_session(session_id: str) -> None:
    with _lock:
        _sessions.pop(session_id, None)
