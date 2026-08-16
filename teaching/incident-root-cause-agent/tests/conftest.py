"""Test-session setup.

Everything in this file runs BEFORE any test module imports
`backend.agent.*` — config.py fail-fast checks and path constants are
computed at import time (module-level singletons), so env vars must be
set here, not inside a fixture, or the first import in the session would
already have locked in the wrong values.

Isolation strategy: state paths (Jira store + both SQLite DBs) are
redirected to a throwaway temp directory via the INCIDENT_AGENT_*_PATH
overrides added to config.py specifically for this. REPOS_DIR is NOT
overridden — tests read the real synthetic repos under data/repos/
(read-only for everything except test_tools.py's apply_patch test, which
uses its own monkeypatched repo dir so it never touches the real fixtures
teaching_brief.md's verified demo run depends on).

OPENAI_API_KEY and INCIDENT_AGENT_API_KEYS are set to obvious dummy
values — no test in this suite makes a real OpenAI call. Every LLM call
site (llm.chat_with_tools / llm.complete_json / llm.embed) is monkeypatched
per-test. If a test is ever written that accidentally calls through to a
real API with these dummy credentials, it fails loudly (401 from OpenAI),
which is the correct failure mode — never silently "worked" with fake data.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

_TEST_STATE_DIR = Path(tempfile.mkdtemp(prefix="incident_agent_test_state_"))

os.environ.setdefault("OPENAI_API_KEY", "sk-test-dummy-not-a-real-key")
os.environ.setdefault("INCIDENT_AGENT_API_KEYS", "test-dummy-key")
os.environ.setdefault("INCIDENT_AGENT_API_KEY", "test-dummy-key")
# Tests must never inherit real Jira credentials from the developer's .env;
# otherwise the production integration path creates external tickets while
# exercising the local mocked-ticket graph tests.
os.environ["JIRA_URL"] = ""
os.environ["JIRA_USERNAME"] = ""
os.environ["JIRA_API_TOKEN"] = ""
os.environ["JIRA_PERSONAL_TOKEN"] = ""
os.environ["INCIDENT_AGENT_JIRA_STORE_PATH"] = str(_TEST_STATE_DIR / "jira" / "tickets.json")
os.environ["INCIDENT_AGENT_INCIDENTS_DB_PATH"] = str(_TEST_STATE_DIR / "db" / "incidents.sqlite")
os.environ["INCIDENT_AGENT_CHECKPOINT_DB_PATH"] = str(_TEST_STATE_DIR / "db" / "checkpoints.sqlite")
# Keep the token budget tight-but-realistic by default; individual budget
# tests override it directly via budget.incident_budget(limit=...).
os.environ.setdefault("INCIDENT_AGENT_MAX_TOKENS_PER_INCIDENT", "60000")

import pytest  # noqa: E402  (must follow the env setup above)


@pytest.fixture(autouse=True)
def _clean_state_between_tests():
    """Each test gets a fresh incidents DB + Jira store — cheap enough
    (SQLite files, not a real service) that per-test isolation is worth it
    over per-session, so one test's data can never leak into another's
    assertions."""
    from backend.agent import db

    db.init_db()
    yield
    with db.get_connection() as conn:
        conn.execute("DELETE FROM incidents")
    store = {"tickets": {}}
    db._save_jira_store(store)


@pytest.fixture(autouse=True)
def _no_real_embed_calls(monkeypatch):
    """Every start_incident() call runs precedent_check -> embed() before
    a test gets anywhere near the thing it's actually testing (budget
    behavior, graph routing, etc). Both tools.py and interface.py did
    `from .llm import embed` at their own import time, so patching
    llm.embed alone does NOT affect either — each needs its own binding
    patched. Deterministic default: a fixed vector, distinct enough that
    two different incident texts still don't spuriously "match" as
    precedents at cosine-similarity 1.0. Tests that care about specific
    embedding/similarity behavior (see test_tools.py's
    TestSearchSimilarIncidents) override this per-test via monkeypatch,
    which layers on top since it's the same monkeypatch instance."""
    from backend.agent import interface as iface_mod
    from backend.agent import tools as tools_mod

    def fake_embed(text: str, model: str | None = None):
        return [float(hash(text) % 997) / 997.0, 0.5, 0.25]

    monkeypatch.setattr(tools_mod, "embed", fake_embed)
    monkeypatch.setattr(iface_mod, "embed", fake_embed)
