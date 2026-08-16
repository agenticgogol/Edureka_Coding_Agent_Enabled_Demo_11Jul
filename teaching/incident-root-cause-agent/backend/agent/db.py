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
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path

from .config import INCIDENTS_DB_PATH, JIRA_STORE_PATH

try:
    import fcntl  # POSIX-only; used for cross-process Jira-store locking
except ImportError:
    fcntl = None  # e.g. Windows — falls back to the in-process lock only

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
    outcome TEXT,
    thread_id TEXT
);
"""

# thread_id was added after initial release — ALTER for any existing DB
# that predates this column (CREATE TABLE IF NOT EXISTS above only applies
# to a fresh DB). Needed so scripts/prune_checkpoints.py can join this
# table (which has created_at + terminal-outcome status) against the
# separate checkpoints DB (which has neither) by thread_id.
_MIGRATIONS = [
    "ALTER TABLE incidents ADD COLUMN thread_id TEXT",
]


@contextmanager
def get_connection():
    conn = sqlite3.connect(str(INCIDENTS_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # WAL + busy_timeout: FastAPI's sync routes run each request in a
    # threadpool, so concurrent reads/writes to this DB are real, not
    # theoretical. Without this, SQLite's default rollback-journal mode
    # serializes all access and a concurrent writer immediately raises
    # "database is locked" instead of waiting.
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(SCHEMA)
        existing_cols = {row["name"] for row in conn.execute("PRAGMA table_info(incidents)")}
        for migration in _MIGRATIONS:
            col_name = migration.split("ADD COLUMN")[1].split()[0]
            if col_name not in existing_cols:
                conn.execute(migration)


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
    thread_id: str | None = None,
) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO incidents (
                id, created_at, incident_text, embedding_json, identified_repo,
                identified_file, root_cause, classification, matched_precedent_id,
                drafted_patch_summary, ticket_id, approval_status, test_result, outcome,
                thread_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                thread_id,
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


def delete_all_incidents() -> int:
    """Wipes the incidents audit table. Used by the UI's 'Reset history'
    action — irreversible (no soft-delete/undo), so callers must gate this
    behind their own confirmation step; this function itself does not ask."""
    with get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM incidents").fetchone()[0]
        conn.execute("DELETE FROM incidents")
        return count


# --- Mocked Jira JSON store -------------------------------------------------
#
# Previously each of create_ticket/close_ticket/reject_ticket did an
# unlocked read-modify-write of the whole file: load -> mutate in memory ->
# overwrite. Under FastAPI's threadpool, two concurrent calls touching
# DIFFERENT tickets could race — both load the same pre-mutation snapshot,
# both write back, and whichever write lands second silently discards the
# other's change (a classic lost update). `_jira_store_lock` below plus a
# best-effort cross-process file lock fixes this: every mutation now
# happens inside one locked load-mutate-save critical section.

_jira_store_lock = threading.Lock()


@contextmanager
def _locked_jira_store():
    """In-process lock (covers this single uvicorn process's threadpool —
    the actual concurrency source per the FastAPI sync-route design) plus
    a best-effort POSIX `flock` (covers the unlikely case of a second
    process pointed at the same data/ dir, e.g. a stray manual script).
    flock is skipped silently on platforms without fcntl (Windows) or if
    it's unavailable — it's defense in depth, not the primary guarantee."""
    with _jira_store_lock:
        Path(JIRA_STORE_PATH).parent.mkdir(parents=True, exist_ok=True)
        lock_path = Path(str(JIRA_STORE_PATH) + ".lock")
        lock_file = open(lock_path, "a+")
        try:
            if fcntl is not None:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            lock_file.close()


def _load_jira_store() -> dict:
    if not Path(JIRA_STORE_PATH).exists():
        return {"tickets": {}}
    with open(JIRA_STORE_PATH) as f:
        return json.load(f)


def _save_jira_store(store: dict) -> None:
    """Atomic write: json.dump to a temp file in the same directory, then
    os.replace() over the real path. `_locked_jira_store()`'s lock already
    stops two writers from racing each other, but it doesn't protect
    against a single writer being interrupted mid-write (process kill,
    OOM) — a direct `open(path, 'w')` + `json.dump` can leave a
    truncated/corrupt JSON file on disk in that case. os.replace() is
    atomic on both POSIX and Windows, so readers only ever see either the
    fully-old or fully-new file, never a partial one."""
    target = Path(JIRA_STORE_PATH)
    tmp_path = target.with_suffix(target.suffix + f".tmp-{os.getpid()}-{threading.get_ident()}")
    with open(tmp_path, "w") as f:
        json.dump(store, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, target)


def create_ticket(ticket_id: str, incident_id: str, summary: str, description: str) -> dict:
    with _locked_jira_store():
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
    with _locked_jira_store():
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
    with _locked_jira_store():
        store = _load_jira_store()
        ticket = store["tickets"].get(ticket_id)
        if ticket is None:
            raise KeyError(f"no such ticket: {ticket_id}")
        ticket["rejection_note"] = rejection_note
        _save_jira_store(store)
        return ticket


def get_ticket(ticket_id: str) -> dict | None:
    with _locked_jira_store():
        store = _load_jira_store()
        return store["tickets"].get(ticket_id)


def delete_all_tickets() -> int:
    """Wipes the mocked Jira ticket store. Part of the UI's 'Reset
    history' action — see delete_all_incidents()'s docstring on the same
    irreversibility/no-confirmation-here contract."""
    with _locked_jira_store():
        store = _load_jira_store()
        count = len(store["tickets"])
        _save_jira_store({"tickets": {}})
        return count
