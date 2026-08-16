"""Unit tests for backend/agent/db.py — incidents table, migration, the
mocked Jira JSON store, WAL mode, and concurrency safety. Uses the
temp-directory DB/Jira paths set up in conftest.py — never touches the
real teaching-demo data."""
from __future__ import annotations

import json
import sqlite3
import threading

import pytest

from backend.agent import db


class TestSchemaAndMigration:
    def test_init_db_is_idempotent(self):
        db.init_db()
        db.init_db()  # must not raise on a second call

    def test_thread_id_column_exists(self):
        with db.get_connection() as conn:
            cols = {row["name"] for row in conn.execute("PRAGMA table_info(incidents)")}
        assert "thread_id" in cols

    def test_journal_mode_is_wal(self):
        with db.get_connection() as conn:
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode.lower() == "wal"


class TestIncidentsCRUD:
    def test_insert_and_get(self):
        db.insert_incident(
            incident_id="inc-1",
            incident_text="checkout API returns 500",
            embedding=[0.1, 0.2],
            identified_repo="checkout-service",
            outcome="closed_pass",
            thread_id="thread-1",
        )
        row = db.get_incident("inc-1")
        assert row is not None
        assert row["incident_text"] == "checkout API returns 500"
        assert row["identified_repo"] == "checkout-service"
        assert row["thread_id"] == "thread-1"
        assert json.loads(row["embedding_json"]) == [0.1, 0.2]

    def test_get_missing_incident_returns_none(self):
        assert db.get_incident("does-not-exist") is None

    def test_update_incident(self):
        db.insert_incident(incident_id="inc-2", incident_text="x", embedding=[0.0])
        db.update_incident("inc-2", outcome="rejected", approval_status="rejected")
        row = db.get_incident("inc-2")
        assert row["outcome"] == "rejected"
        assert row["approval_status"] == "rejected"

    def test_update_with_no_fields_is_a_noop(self):
        db.insert_incident(incident_id="inc-3", incident_text="x", embedding=[0.0])
        db.update_incident("inc-3")  # must not raise
        assert db.get_incident("inc-3") is not None

    def test_all_incidents_ordered_most_recent_first(self):
        db.insert_incident(incident_id="inc-a", incident_text="first", embedding=[0.0])
        db.insert_incident(incident_id="inc-b", incident_text="second", embedding=[0.0])
        rows = db.all_incidents()
        ids = [r["id"] for r in rows]
        assert ids.index("inc-b") < ids.index("inc-a")

    def test_insert_or_replace_on_duplicate_id(self):
        db.insert_incident(incident_id="inc-dup", incident_text="v1", embedding=[0.0])
        db.insert_incident(incident_id="inc-dup", incident_text="v2", embedding=[0.0])
        row = db.get_incident("inc-dup")
        assert row["incident_text"] == "v2"
        assert len(db.all_incidents()) == 1


class TestJiraStore:
    def test_create_ticket(self):
        ticket = db.create_ticket("TCKT-1", "inc-1", "summary", "description")
        assert ticket["ticket_id"] == "TCKT-1"
        assert ticket["status"] == "open"
        assert db.get_ticket("TCKT-1") == ticket

    def test_create_ticket_idempotent(self):
        t1 = db.create_ticket("TCKT-dup", "inc-1", "summary A", "desc A")
        t2 = db.create_ticket("TCKT-dup", "inc-1", "summary B (should be ignored)", "desc B")
        assert t1 == t2
        assert t2["summary"] == "summary A"  # first write wins, second is a no-op

    def test_close_ticket(self):
        db.create_ticket("TCKT-close", "inc-1", "s", "d")
        closed = db.close_ticket("TCKT-close", "fixed it")
        assert closed["status"] == "closed"
        assert closed["resolution_note"] == "fixed it"
        assert closed["closed_at"] is not None

    def test_close_ticket_idempotent(self):
        db.create_ticket("TCKT-close2", "inc-1", "s", "d")
        db.close_ticket("TCKT-close2", "first close")
        second = db.close_ticket("TCKT-close2", "second close attempt")
        assert second["resolution_note"] == "first close"  # unchanged, no-op per stage 4

    def test_close_missing_ticket_raises(self):
        with pytest.raises(KeyError):
            db.close_ticket("TCKT-does-not-exist", "note")

    def test_reject_ticket_leaves_open(self):
        db.create_ticket("TCKT-reject", "inc-1", "s", "d")
        rejected = db.reject_ticket("TCKT-reject", "not a real fix")
        assert rejected["rejection_note"] == "not a real fix"
        assert db.get_ticket("TCKT-reject")["status"] == "open"

    def test_save_is_atomic_no_tmp_file_left_behind(self):
        from pathlib import Path

        from backend.agent.config import JIRA_STORE_PATH

        db.create_ticket("TCKT-atomic", "inc-1", "s", "d")
        leftovers = [
            p for p in Path(JIRA_STORE_PATH).parent.iterdir() if "tmp" in p.name
        ]
        assert leftovers == []

    def test_concurrent_ticket_creation_no_lost_writes(self):
        # Regression test for the lost-update race found in the
        # production-readiness audit: concurrent create_ticket calls for
        # DIFFERENT tickets used to race on an unlocked read-modify-write
        # of the whole tickets.json file, silently dropping some writes.
        errors: list[Exception] = []

        def make(i: int) -> None:
            try:
                db.create_ticket(f"TCKT-concur-{i}", f"inc-{i}", f"s{i}", f"d{i}")
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=make, args=(i,)) for i in range(25)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        for i in range(25):
            assert db.get_ticket(f"TCKT-concur-{i}") is not None

    def test_concurrent_incident_inserts_no_database_locked_error(self):
        # Regression test for SQLite's default rollback-journal mode
        # serializing writers and raising "database is locked" under
        # FastAPI's threadpool concurrency — WAL mode + busy_timeout fixes
        # this (see get_connection()).
        errors: list[Exception] = []

        def insert(i: int) -> None:
            try:
                db.insert_incident(incident_id=f"inc-concur-{i}", incident_text=f"t{i}", embedding=[0.0])
            except sqlite3.OperationalError as exc:
                errors.append(exc)

        threads = [threading.Thread(target=insert, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        assert len(db.all_incidents()) == 20


class TestResetHistory:
    def test_delete_all_incidents_returns_count_and_empties_table(self):
        db.insert_incident(incident_id="r1", incident_text="a", embedding=[0.0])
        db.insert_incident(incident_id="r2", incident_text="b", embedding=[0.0])
        deleted = db.delete_all_incidents()
        assert deleted == 2
        assert db.all_incidents() == []

    def test_delete_all_incidents_on_empty_table_returns_zero(self):
        assert db.delete_all_incidents() == 0

    def test_delete_all_tickets_returns_count_and_empties_store(self):
        db.create_ticket("TCKT-r1", "inc-1", "s", "d")
        db.create_ticket("TCKT-r2", "inc-2", "s", "d")
        deleted = db.delete_all_tickets()
        assert deleted == 2
        assert db.get_ticket("TCKT-r1") is None
        assert db.get_ticket("TCKT-r2") is None

    def test_reset_does_not_affect_unrelated_future_writes(self):
        # After a reset, the DB must still be fully usable — not left in
        # some half-torn state.
        db.insert_incident(incident_id="pre-reset", incident_text="x", embedding=[0.0])
        db.delete_all_incidents()
        db.insert_incident(incident_id="post-reset", incident_text="y", embedding=[0.0])
        assert len(db.all_incidents()) == 1
        assert db.get_incident("post-reset") is not None
