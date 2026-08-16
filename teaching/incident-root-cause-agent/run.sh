#!/usr/bin/env bash
# Run the incident-root-cause-agent backend + frontend together.
# Must be run from teaching/incident-root-cause-agent/.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

VENV=".venv"
BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-8501}"

# backend/agent/config.py loads .env itself via python-dotenv (walks up
# from this dir to find the repo root .env). frontend/app.py does NOT —
# it reads os.environ directly — so export the repo-root .env here for
# both processes, in particular INCIDENT_AGENT_API_KEY for the frontend.
ROOT_ENV="../../.env"
if [ -f "$ROOT_ENV" ]; then
  set -a
  # shellcheck disable=SC1090
  source "$ROOT_ENV"
  set +a
fi

if [ ! -d "$VENV" ]; then
  echo "No $VENV found — creating it with python3.11 and installing requirements..."
  python3.11 -m venv "$VENV"
  "$VENV/bin/pip" install -r backend/requirements.txt -r frontend/requirements.txt
fi

port_in_use() {
  lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1
}

if port_in_use "$BACKEND_PORT"; then
  echo "Port $BACKEND_PORT is already in use. Stop the existing backend or set BACKEND_PORT to another free port."
  exit 1
fi

if port_in_use "$FRONTEND_PORT"; then
  echo "Port $FRONTEND_PORT is already in use. Stop the existing frontend or set FRONTEND_PORT to another free port."
  exit 1
fi

cleanup() {
  echo
  echo "Stopping backend and frontend..."
  [ -n "${BACKEND_PID:-}" ] && kill "$BACKEND_PID" 2>/dev/null || true
  [ -n "${FRONTEND_PID:-}" ] && kill "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "Starting backend on http://${BACKEND_HOST}:${BACKEND_PORT} ..."
"$VENV/bin/uvicorn" backend.main:app --reload --host "$BACKEND_HOST" --port "$BACKEND_PORT" &
BACKEND_PID=$!

# Give the backend a moment to fail fast on a missing API key before
# launching the frontend against it.
sleep 2

if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
  echo "Backend failed to start; frontend will not be launched."
  exit 1
fi

echo "Starting frontend on http://localhost:${FRONTEND_PORT} ..."
"$VENV/bin/streamlit" run frontend/app.py --server.port "$FRONTEND_PORT" &
FRONTEND_PID=$!

wait "$BACKEND_PID" "$FRONTEND_PID"
