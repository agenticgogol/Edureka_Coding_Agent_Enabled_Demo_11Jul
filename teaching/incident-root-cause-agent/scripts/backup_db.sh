#!/usr/bin/env bash
# Back up both SQLite DBs + the mocked Jira JSON store.
#
# Uses `sqlite3 .backup` (not a raw file copy) so a backup taken while the
# backend is running mid-write is still a consistent snapshot, not a
# torn/corrupt file. Run on a cron/systemd-timer schedule in production —
# see the README's "Persistence lifecycle" section for a suggested cadence.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

BACKUP_ROOT="${INCIDENT_AGENT_BACKUP_DIR:-backups}"
STAMP="$(date +%Y%m%d_%H%M%S)"
DEST="$BACKUP_ROOT/$STAMP"
mkdir -p "$DEST"

if command -v sqlite3 >/dev/null 2>&1; then
  sqlite3 data/db/incidents.sqlite ".backup '$DEST/incidents.sqlite'"
  sqlite3 data/db/checkpoints.sqlite ".backup '$DEST/checkpoints.sqlite'"
else
  echo "sqlite3 CLI not found — falling back to plain file copy (only safe" >&2
  echo "if the backend is stopped, since it isn't a transactionally" >&2
  echo "consistent snapshot of a live DB)." >&2
  cp data/db/incidents.sqlite "$DEST/incidents.sqlite"
  cp data/db/checkpoints.sqlite "$DEST/checkpoints.sqlite"
fi

cp data/jira/tickets.json "$DEST/tickets.json" 2>/dev/null || true

echo "Backed up to $DEST"

# Retention: keep the last N backup directories, delete older ones.
KEEP="${INCIDENT_AGENT_BACKUP_KEEP:-14}"
ls -1dt "$BACKUP_ROOT"/*/ 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm -rf
