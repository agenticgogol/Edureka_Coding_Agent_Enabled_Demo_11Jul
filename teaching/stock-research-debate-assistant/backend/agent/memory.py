"""Long-term memory (SQLite) read/write functions.

This module owns only the read/write *functions* — the backend-builder
wires the FastAPI persistence layer (which user_key to pass, when to call
these) around this interface. DB file defaults to
`backend/data/memory.db` (see config.memory_db_path), created on first use.

Two tables:
- `risk_tolerance(user_key PRIMARY KEY, value, updated_at)`
- `ticker_analysis(ticker PRIMARY KEY, synthesis, stance, updated_at)`

Both writes are upserts (no deletes in Milestone 1), matching the
architecture design's idempotency note for this tool.
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone

from .config import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS risk_tolerance (
    user_key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ticker_analysis (
    ticker TEXT PRIMARY KEY,
    synthesis TEXT NOT NULL,
    stance TEXT,
    updated_at TEXT NOT NULL
);
"""


def _connect() -> sqlite3.Connection:
    db_path = config.memory_db_path
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(_SCHEMA)
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_risk_tolerance(user_key: str) -> str | None:
    with closing(_connect()) as conn:
        row = conn.execute(
            "SELECT value FROM risk_tolerance WHERE user_key = ?", (user_key,)
        ).fetchone()
        return row[0] if row else None


def save_risk_tolerance(user_key: str, value: str) -> None:
    with closing(_connect()) as conn:
        conn.execute(
            """
            INSERT INTO risk_tolerance (user_key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """,
            (user_key, value, _now()),
        )
        conn.commit()


def get_past_analysis(ticker: str) -> dict | None:
    with closing(_connect()) as conn:
        row = conn.execute(
            "SELECT ticker, synthesis, stance, updated_at FROM ticker_analysis WHERE ticker = ?",
            (ticker.upper(),),
        ).fetchone()
        if not row:
            return None
        return {"ticker": row[0], "synthesis": row[1], "stance": row[2], "updated_at": row[3]}


def save_analysis(ticker: str, synthesis: str, stance: str | None = None) -> None:
    with closing(_connect()) as conn:
        conn.execute(
            """
            INSERT INTO ticker_analysis (ticker, synthesis, stance, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(ticker) DO UPDATE SET
                synthesis = excluded.synthesis,
                stance = excluded.stance,
                updated_at = excluded.updated_at
            """,
            (ticker.upper(), synthesis, stance, _now()),
        )
        conn.commit()
