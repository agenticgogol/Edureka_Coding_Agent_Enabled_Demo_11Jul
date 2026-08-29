#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [[ -n "${PYTHON_BIN:-}" ]]; then
  PYTHON_BIN="$PYTHON_BIN"
elif command -v python3.12 >/dev/null 2>&1; then
  PYTHON_BIN="python3.12"
else
  PYTHON_BIN="python3"
fi
VENV_DIR="${VENV_DIR:-$SCRIPT_DIR/.venv-3.12}"
BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-8501}"
BACKEND_URL="${BACKEND_URL:-http://${BACKEND_HOST}:${BACKEND_PORT}}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python executable not found: $PYTHON_BIN" >&2
  exit 1
fi

if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  echo "Creating virtual environment at $VENV_DIR"
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

VENV_PYTHON="$VENV_DIR/bin/python"
echo "Installing backend and frontend requirements..."
"$VENV_PYTHON" -m pip install --no-cache-dir -r backend/requirements.txt -r frontend/requirements.txt

cleanup() {
  if [[ -n "${BACKEND_PID:-}" ]] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo "Stopping backend..."
    kill "$BACKEND_PID" 2>/dev/null || true
    wait "$BACKEND_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

echo "Starting FastAPI backend at $BACKEND_URL"
BACKEND_URL="$BACKEND_URL" "$VENV_PYTHON" -m uvicorn backend.main:app \
  --host "$BACKEND_HOST" --port "$BACKEND_PORT" --reload &
BACKEND_PID=$!

echo "Waiting for backend health check..."
for _ in {1..60}; do
  if "$VENV_PYTHON" -c "import urllib.request; urllib.request.urlopen('${BACKEND_URL}/health', timeout=2)" >/dev/null 2>&1; then
    break
  fi
  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo "Backend stopped before becoming healthy." >&2
    exit 1
  fi
  sleep 1
done

if ! "$VENV_PYTHON" -c "import urllib.request; urllib.request.urlopen('${BACKEND_URL}/health', timeout=2)" >/dev/null 2>&1; then
  echo "Backend health check failed at ${BACKEND_URL}/health" >&2
  exit 1
fi

echo "Starting Streamlit frontend at http://localhost:${FRONTEND_PORT}"
BACKEND_URL="$BACKEND_URL" "$VENV_PYTHON" -m streamlit run frontend/app.py \
  --server.port "$FRONTEND_PORT" --server.address 0.0.0.0
