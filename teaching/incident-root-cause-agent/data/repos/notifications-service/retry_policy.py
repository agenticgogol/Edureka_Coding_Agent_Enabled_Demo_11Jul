"""Retry/backoff policy for failed notification sends (synthetic, working
code)."""
from __future__ import annotations

MAX_RETRIES = 3
BASE_BACKOFF_SECONDS = 2


def backoff_delay(attempt: int) -> int:
    if attempt < 1:
        raise ValueError("attempt must be >= 1")
    return BASE_BACKOFF_SECONDS * (2 ** (attempt - 1))


def should_retry(attempt: int) -> bool:
    return attempt < MAX_RETRIES
