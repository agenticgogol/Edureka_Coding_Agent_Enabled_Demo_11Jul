"""SQLite persistence: the `incidents` table (audit history + precedent
store, per design.md stage 5) and the mocked Jira JSON store.

The LangGraph checkpointer (task/scratch state across the approval
interrupt) lives in a *separate* SQLite file (`CHECKPOINT_DB_PATH`) so the
two long-retention audit tables and the transient per-thread graph
checkpoints don't share a schema — see `graph.py` for the checkpointer.
Both files live under `data/db/` and both survive a process restart
because they're on disk.
"""
from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

from .config import INCIDENTS_DB_PATH, JIRA_STORE_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS incidents (
    id TEXT PRIMARY KEY,
    created_at REAL NOT NULL,
    incident_text TEXT NOT NULL,
    embedding_json TEXT NOT NULL,
    identified_repo TEXT,
    identified_file TEXT,
    root_cause TEXT,
    classification TEXT,
    matched_precedent_id TEXT,
    drafted_patch_summary TEXT,
    ticket_id TEXT,
    approval_status TEXT,
    test_result TEXT,
    outcome TEXT
);
"""


@contextmanager
def get_connection():
    conn = sqlite3.connect(str(INCIDENTS_DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(SCHEMA)


def insert_incident(
    incident_id: str,
    incident_text: str,
    embedding: list[float],
    identified_repo: str | None = None,
    identified_file: str | None = None,
    root_cause: str | None = None,
    classification: str | None = None,
    matched_precedent_id: str | None = None,
    drafted_patch_summary: str | None = None,
    ticket_id: str | None = None,
    approval_status: str | None = None,
    test_result: str | None = None,
    outcome: str | None = None,
) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO incidents (
                id, created_at, incident_text, embedding_json, identified_repo,
                identified_file, root_cause, classification, matched_precedent_id,
                drafted_patch_summary, ticket_id, approval_status, test_result, outcome
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                incident_id,
                time.time(),
                incident_text,
                json.dumps(embedding),
                identified_repo,
                identified_file,
                root_cause,
                classification,
                matched_precedent_id,
                drafted_patch_summary,
                ticket_id,
                approval_status,
                test_result,
                outcome,
            ),
        )


def update_incident(incident_id: str, **fields) -> None:
    if not fields:
        return
    columns = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [incident_id]
    with get_connection() as conn:
        conn.execute(f"UPDATE incidents SET {columns} WHERE id = ?", values)


def all_incidents() -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute("SELECT * FROM incidents ORDER BY created_at DESC").fetchall()


def get_incident(incident_id: str) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,)).fetchone()


# --- Mocked Jira JSON store -------------------------------------------------


def _load_jira_store() -> dict:
    if not Path(JIRA_STORE_PATH).exists():
        return {"tickets": {}}
    with open(JIRA_STORE_PATH) as f:
        return json.load(f)


def _save_jira_store(store: dict) -> None:
    with open(JIRA_STORE_PATH, "w") as f:
        json.dump(store, f, indent=2)


def create_ticket(ticket_id: str, incident_id: str, summary: str, description: str) -> dict:
    store = _load_jira_store()
    if ticket_id in store["tickets"]:
        # Idempotent: creating the same ticket key twice (e.g. on a retry
        # after a transient failure) is a no-op, per stage 4's tool table.
        return store["tickets"][ticket_id]
    ticket = {
        "ticket_id": ticket_id,
        "incident_id": incident_id,
        "summary": summary,
        "description": description,
        "status": "open",
        "created_at": time.time(),
        "closed_at": None,
        "rejection_note": None,
    }
    store["tickets"][ticket_id] = ticket
    _save_jira_store(store)
    return ticket


def close_ticket(ticket_id: str, resolution_note: str) -> dict:
    store = _load_jira_store()
    ticket = store["tickets"].get(ticket_id)
    if ticket is None:
        raise KeyError(f"no such ticket: {ticket_id}")
    if ticket["status"] == "closed":
        return ticket  # idempotent no-op per stage 4
    ticket["status"] = "closed"
    ticket["closed_at"] = time.time()
    ticket["resolution_note"] = resolution_note
    _save_jira_store(store)
    return ticket


def reject_ticket(ticket_id: str, rejection_note: str) -> dict:
    """Leaves the ticket open but records the rejection, per termination
    condition 5 in `07_loop_engineering.md`."""
    store = _load_jira_store()
    ticket = store["tickets"].get(ticket_id)
    if ticket is None:
        raise KeyError(f"no such ticket: {ticket_id}")
    ticket["rejection_note"] = rejection_note
    _save_jira_store(store)
    return ticket


def get_ticket(ticket_id: str) -> dict | None:
    store = _load_jira_store()
    return store["tickets"].get(ticket_id)
