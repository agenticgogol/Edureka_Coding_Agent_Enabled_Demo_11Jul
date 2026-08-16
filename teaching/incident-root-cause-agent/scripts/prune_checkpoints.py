#!/usr/bin/env python3
"""Prune LangGraph checkpoint growth in data/db/checkpoints.sqlite.

The checkpointer writes a new row per graph step and never deletes old
ones (see backend/agent/graph.py's get_checkpointer_cm) — left alone this
file grows unbounded forever. Two independent, composable prunes:

1. --compact (safe to run anytime, even on active threads): for every
   thread_id, keep only the N most recent checkpoints (default 1) and
   delete the rest, plus their associated `writes` rows. The approval/
   resume flow only ever needs the latest checkpoint to resume — older
   ones are only useful for LangGraph time-travel/debugging, which this
   demo doesn't use.

2. --delete-terminal-older-than-days N: fully delete every checkpoint (and
   writes row) for threads whose linked incident (via incidents.thread_id
   — see db.py's schema) is in a terminal outcome AND older than N days.
   Incidents with no thread_id recorded (pre-migration rows) are skipped,
   not guessed at.

Run via cron/systemd-timer alongside backup_db.sh — back up BEFORE
pruning, not after, so a bad prune is recoverable.

Usage:
    python scripts/prune_checkpoints.py --compact
    python scripts/prune_checkpoints.py --compact --keep 3
    python scripts/prune_checkpoints.py --delete-terminal-older-than-days 30
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parent.parent
CHECKPOINT_DB = MODULE_ROOT / "data" / "db" / "checkpoints.sqlite"
INCIDENTS_DB = MODULE_ROOT / "data" / "db" / "incidents.sqlite"

_TERMINAL_OUTCOMES = {
    "infra_resolved",
    "closed_pass",
    "rejected",
    "test_failed_after_retry",
    "escalated_ceiling",
}


def compact(keep: int) -> None:
    """Keep only the `keep` most recent checkpoints per thread_id/ns."""
    conn = sqlite3.connect(str(CHECKPOINT_DB))
    try:
        threads = conn.execute(
            "SELECT DISTINCT thread_id, checkpoint_ns FROM checkpoints"
        ).fetchall()
        total_deleted = 0
        for thread_id, ns in threads:
            rows = conn.execute(
                """
                SELECT checkpoint_id FROM checkpoints
                WHERE thread_id = ? AND checkpoint_ns = ?
                ORDER BY checkpoint_id DESC
                """,
                (thread_id, ns),
            ).fetchall()
            # checkpoint_id is a lexicographically time-sortable UUID
            # (LangGraph uses UUIDv6) — DESC order is newest-first.
            stale_ids = [r[0] for r in rows[keep:]]
            for cp_id in stale_ids:
                conn.execute(
                    "DELETE FROM writes WHERE thread_id = ? AND checkpoint_ns = ? AND checkpoint_id = ?",
                    (thread_id, ns, cp_id),
                )
                conn.execute(
                    "DELETE FROM checkpoints WHERE thread_id = ? AND checkpoint_ns = ? AND checkpoint_id = ?",
                    (thread_id, ns, cp_id),
                )
            total_deleted += len(stale_ids)
        conn.commit()
        print(f"compact: deleted {total_deleted} stale checkpoint(s) across {len(threads)} thread(s), kept up to {keep} each")
    finally:
        conn.close()


def delete_terminal_older_than(days: int) -> None:
    cutoff = time.time() - days * 86400

    incidents_conn = sqlite3.connect(str(INCIDENTS_DB))
    incidents_conn.row_factory = sqlite3.Row
    try:
        rows = incidents_conn.execute(
            "SELECT thread_id, outcome, created_at FROM incidents WHERE thread_id IS NOT NULL"
        ).fetchall()
    finally:
        incidents_conn.close()

    eligible_thread_ids = [
        r["thread_id"]
        for r in rows
        if r["outcome"] in _TERMINAL_OUTCOMES and r["created_at"] < cutoff
    ]

    if not eligible_thread_ids:
        print(f"delete-terminal-older-than-days {days}: nothing eligible")
        return

    conn = sqlite3.connect(str(CHECKPOINT_DB))
    try:
        placeholders = ",".join("?" * len(eligible_thread_ids))
        conn.execute(f"DELETE FROM writes WHERE thread_id IN ({placeholders})", eligible_thread_ids)
        cur = conn.execute(
            f"DELETE FROM checkpoints WHERE thread_id IN ({placeholders})", eligible_thread_ids
        )
        conn.commit()
        print(f"delete-terminal-older-than-days {days}: removed checkpoints for {len(eligible_thread_ids)} thread(s)")
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--compact", action="store_true", help="keep only the N most recent checkpoints per thread")
    parser.add_argument("--keep", type=int, default=1, help="checkpoints to keep per thread with --compact (default 1)")
    parser.add_argument(
        "--delete-terminal-older-than-days",
        type=int,
        default=None,
        metavar="N",
        help="fully delete checkpoints for terminal incidents older than N days",
    )
    args = parser.parse_args()

    if not CHECKPOINT_DB.exists():
        print(f"no checkpoint DB at {CHECKPOINT_DB} — nothing to prune", file=sys.stderr)
        return

    if not args.compact and args.delete_terminal_older_than_days is None:
        parser.error("pass --compact and/or --delete-terminal-older-than-days N")

    if args.compact:
        compact(args.keep)
    if args.delete_terminal_older_than_days is not None:
        delete_terminal_older_than(args.delete_terminal_older_than_days)


if __name__ == "__main__":
    main()
