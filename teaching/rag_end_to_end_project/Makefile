.PHONY: install run run-backend run-frontend stop clean

VENV := .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
BACKEND_PORT := 8000
FRONTEND_PORT := 8501

# Requires python3.11 or python3.12 on PATH — tiktoken/pydantic-core have
# no prebuilt wheels for newer Pythons yet (see README.md).
install:
	python3.11 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

# Runs backend + frontend together in one terminal: backend starts first,
# frontend follows once /health responds, and Ctrl-C stops both.
run:
	@trap 'kill 0' EXIT INT TERM; \
	$(VENV)/bin/uvicorn backend.main:app --port $(BACKEND_PORT) & \
	echo "Waiting for backend on :$(BACKEND_PORT)..."; \
	until curl -sf http://localhost:$(BACKEND_PORT)/health > /dev/null 2>&1; do sleep 0.5; done; \
	echo "Backend up. Starting frontend on :$(FRONTEND_PORT)..."; \
	$(VENV)/bin/streamlit run frontend/app.py --server.port $(FRONTEND_PORT) & \
	wait

run-backend:
	$(VENV)/bin/uvicorn backend.main:app --reload --port $(BACKEND_PORT)

run-frontend:
	$(VENV)/bin/streamlit run frontend/app.py --server.port $(FRONTEND_PORT)

# Kills anything left listening on the backend/frontend ports (useful if
# `make run` was interrupted uncleanly).
stop:
	-lsof -ti:$(BACKEND_PORT) | xargs -r kill -9
	-lsof -ti:$(FRONTEND_PORT) | xargs -r kill -9

clean:
	rm -rf $(VENV) backend/__pycache__ frontend/__pycache__ **/__pycache__
