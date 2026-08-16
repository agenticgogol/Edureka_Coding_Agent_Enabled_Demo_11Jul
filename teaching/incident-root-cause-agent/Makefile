PYTHON := python3.11
VENV := .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

.PHONY: help venv install install-test test seed backend frontend run clean

help:
	@echo "Targets:"
	@echo "  make venv         - create $(VENV) with $(PYTHON)"
	@echo "  make install      - install backend + frontend requirements into $(VENV)"
	@echo "  make install-test - install pytest into $(VENV) (not needed for running the app)"
	@echo "  make test         - run the unit test suite (no real API calls, all LLM calls mocked)"
	@echo "  make seed         - seed one prior resolved incident (1 real embedding call)"
	@echo "  make backend      - run the FastAPI backend on http://127.0.0.1:8000"
	@echo "  make frontend     - run the Streamlit UI on http://localhost:8501"
	@echo "  make run          - run backend + frontend together (Ctrl+C stops both)"
	@echo "  make clean        - remove $(VENV) and __pycache__ dirs"

venv:
	$(PYTHON) -m venv $(VENV)

install: venv
	$(PIP) install -r backend/requirements.txt -r frontend/requirements.txt

install-test: venv
	$(PIP) install -r requirements-test.txt

test: install-test
	$(VENV)/bin/pytest tests/ -v

seed:
	$(PY) -m backend.agent.seed_data

backend:
	$(VENV)/bin/uvicorn backend.main:app --reload

frontend:
	@# frontend/app.py reads os.environ directly (no python-dotenv) — export
	@# the repo-root .env so INCIDENT_AGENT_API_KEY/BACKEND_URL are visible.
	@set -a && . ../../.env && set +a && $(VENV)/bin/streamlit run frontend/app.py

run:
	./run.sh

clean:
	rm -rf $(VENV)
	find . -name "__pycache__" -type d -exec rm -rf {} +
