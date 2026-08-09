"""Simple in-memory rate limiter for auth-service login attempts
(synthetic, working code)."""
from __future__ import annotations

import time

_ATTEMPTS: dict[str, list[float]] = {}
WINDOW_SECONDS = 60
MAX_ATTEMPTS = 5


def record_attempt(user_id: str) -> None:
    now = time.time()
    _ATTEMPTS.setdefault(user_id, [])
    _ATTEMPTS[user_id] = [t for t in _ATTEMPTS[user_id] if now - t < WINDOW_SECONDS]
    _ATTEMPTS[user_id].append(now)


def is_rate_limited(user_id: str) -> bool:
    now = time.time()
    attempts = [t for t in _ATTEMPTS.get(user_id, []) if now - t < WINDOW_SECONDS]
    return len(attempts) > MAX_ATTEMPTS
