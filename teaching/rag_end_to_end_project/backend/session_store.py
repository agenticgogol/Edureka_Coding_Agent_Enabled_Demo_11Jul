"""In-memory session state, keyed by session_id.

Holds chat history (list of {role, content} turns) and a running cost
total per session. Lost on server restart — acceptable for a live
teaching demo (same pattern as basic_end_to_end_chatbot).
"""
from __future__ import annotations

from threading import Lock

_sessions: dict[str, list[dict]] = {}
_costs: dict[str, float] = {}
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
        _costs.pop(session_id, None)


def add_cost(session_id: str, amount: float) -> float:
    """Adds amount to the session's running total and returns the new total."""
    with _lock:
        total = _costs.get(session_id, 0.0) + amount
        _costs[session_id] = total
        return total


def get_total_cost(session_id: str) -> float:
    with _lock:
        return _costs.get(session_id, 0.0)
