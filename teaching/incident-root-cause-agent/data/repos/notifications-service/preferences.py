"""User notification preferences for notifications-service (synthetic,
working code)."""
from __future__ import annotations

# Synthetic in-memory preferences: user_id -> set of opted-in channels.
PREFERENCES: dict[str, set[str]] = {}


def set_preference(user_id: str, channel: str, enabled: bool) -> None:
    PREFERENCES.setdefault(user_id, set())
    if enabled:
        PREFERENCES[user_id].add(channel)
    else:
        PREFERENCES[user_id].discard(channel)


def is_opted_in(user_id: str, channel: str) -> bool:
    return channel in PREFERENCES.get(user_id, set())
