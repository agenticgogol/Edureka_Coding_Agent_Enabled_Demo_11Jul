"""Config/env loading for the incident-root-cause-agent module.

Copied from this repo's `_shared/config.py` template (per `helper-utils`),
trimmed to the keys this agent actually reads. No mock mode: importing
this module raises immediately if OPENAI_API_KEY is not set — this
project's design.md requires OpenAI for both the reasoning model and
embeddings, so we require that key specifically rather than "any LLM key".
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass  # dotenv is optional; env vars can also come from the shell/host


class MissingAPIKeyError(RuntimeError):
    """Raised when OPENAI_API_KEY is not configured. There is no mock
    fallback in this repo — this must stop execution, not be caught and
    papered over."""


AGENT_DIR = Path(__file__).resolve().parent
MODULE_ROOT = AGENT_DIR.parent.parent  # teaching/incident-root-cause-agent/
DATA_DIR = MODULE_ROOT / "data"
REPOS_DIR = DATA_DIR / "repos"

# State paths (Jira store + both SQLite DBs) are independently
# env-overridable — the test suite (tests/conftest.py) points these at a
# throwaway temp directory so tests never read/write the real demo data
# in data/db and data/jira. REPOS_DIR is deliberately NOT overridable the
# same way: it's the fixed set of synthetic repos the agent searches, and
# most tests read those directly (safe — read-only for everything except
# the one apply_patch test, which uses its own monkeypatched repo dir).
JIRA_STORE_PATH = Path(
    os.environ.get("INCIDENT_AGENT_JIRA_STORE_PATH", str(DATA_DIR / "jira" / "tickets.json"))
)
INCIDENTS_DB_PATH = Path(
    os.environ.get("INCIDENT_AGENT_INCIDENTS_DB_PATH", str(DATA_DIR / "db" / "incidents.sqlite"))
)
CHECKPOINT_DB_PATH = Path(
    os.environ.get("INCIDENT_AGENT_CHECKPOINT_DB_PATH", str(DATA_DIR / "db" / "checkpoints.sqlite"))
)

REASONING_MODEL = os.environ.get("INCIDENT_AGENT_MODEL", "gpt-4o-mini")
EMBEDDING_MODEL = os.environ.get("INCIDENT_AGENT_EMBEDDING_MODEL", "text-embedding-3-small")

ALLOWED_REPOS = ("checkout-service", "auth-service", "notifications-service")

# --- Precedent matching (tools.py search_similar_incidents) -----------------
# Lowered from the original 0.80: a verified real run showed a legitimately
# paraphrased duplicate ("checkout API returns 500 on large carts" vs. the
# seeded precedent's fuller description) scored 0.78 cosine similarity —
# just under the old bar despite describing the same incident. 0.75 catches
# that case while still requiring genuine semantic closeness, not just
# shared keywords.
PRECEDENT_SIMILARITY_THRESHOLD = float(
    os.environ.get("INCIDENT_AGENT_PRECEDENT_SIMILARITY_THRESHOLD", "0.75")
)

# --- Cost / rate controls (budget.py) ---------------------------------------
MAX_TOKENS_PER_INCIDENT = int(os.environ.get("INCIDENT_AGENT_MAX_TOKENS_PER_INCIDENT", "60000"))
RATE_LIMIT_PER_MINUTE = int(os.environ.get("INCIDENT_AGENT_RATE_LIMIT_PER_MIN", "10"))
RATE_LIMIT_WINDOW_SECONDS = 60

# --- LLM client retry/timeout (llm.py) --------------------------------------
OPENAI_TIMEOUT_SECONDS = float(os.environ.get("INCIDENT_AGENT_OPENAI_TIMEOUT", "60"))
OPENAI_MAX_RETRIES = int(os.environ.get("INCIDENT_AGENT_OPENAI_MAX_RETRIES", "3"))

# --- Auth (auth.py) ----------------------------------------------------------
# Comma-separated list of accepted API keys for the FastAPI backend. Empty
# by default so a fresh checkout fails loudly (see auth.py) rather than
# silently running unauthenticated.
API_KEYS = tuple(
    k.strip() for k in os.environ.get("INCIDENT_AGENT_API_KEYS", "").split(",") if k.strip()
)

# --- Sandboxing (tools.py run_tests) ----------------------------------------
RUN_TESTS_TIMEOUT_SECONDS = int(os.environ.get("INCIDENT_AGENT_RUN_TESTS_TIMEOUT", "30"))
RUN_TESTS_MAX_MEMORY_BYTES = int(
    os.environ.get("INCIDENT_AGENT_RUN_TESTS_MAX_MEMORY_MB", "256")
) * 1024 * 1024
RUN_TESTS_MAX_CPU_SECONDS = int(os.environ.get("INCIDENT_AGENT_RUN_TESTS_MAX_CPU_SECONDS", "10"))

# --- Real Jira via MCP (backend/agent/mcp_jira.py) --------------------------
# Opt-in: the mocked local JSON ticket store (db.py) remains the default —
# real Jira activates when JIRA_URL plus either Cloud basic-auth credentials
# (JIRA_USERNAME + JIRA_API_TOKEN) or a Server/Data Center PAT
# (JIRA_PERSONAL_TOKEN) are set. No new required vars for existing users.
JIRA_PROJECT_KEY = os.environ.get("JIRA_PROJECT_KEY", "SCRUM")
JIRA_ISSUE_TYPE = os.environ.get("INCIDENT_AGENT_JIRA_ISSUE_TYPE", "Task")
MCP_ATLASSIAN_PACKAGE = os.environ.get(
    "INCIDENT_AGENT_MCP_ATLASSIAN_PACKAGE", "mcp-atlassian>=0.22.0"
)
MCP_UV_CACHE_DIR = os.environ.get(
    "INCIDENT_AGENT_UV_CACHE_DIR", "/tmp/incident-root-cause-agent-uv-cache"
)
MCP_UV_TOOL_DIR = os.environ.get(
    "INCIDENT_AGENT_UV_TOOL_DIR", "/tmp/incident-root-cause-agent-uv-tools"
)
# Must match a real transition name in your project's workflow (Jira's
# default Kanban/Scrum templates both use "Done") — configurable since
# custom workflows often rename or split this.
JIRA_DONE_TRANSITION_NAME = os.environ.get("INCIDENT_AGENT_JIRA_DONE_TRANSITION_NAME", "Done")


@dataclass(frozen=True)
class Config:
    openai_api_key: str = field(default_factory=lambda: os.environ.get("OPENAI_API_KEY", ""))

    phoenix_collector_endpoint: str = field(
        default_factory=lambda: os.environ.get("PHOENIX_COLLECTOR_ENDPOINT", "")
    )
    phoenix_api_key: str = field(default_factory=lambda: os.environ.get("PHOENIX_API_KEY", ""))

    jira_url: str = field(default_factory=lambda: os.environ.get("JIRA_URL", "").rstrip("/"))
    jira_username: str = field(default_factory=lambda: os.environ.get("JIRA_USERNAME", ""))
    jira_api_token: str = field(default_factory=lambda: os.environ.get("JIRA_API_TOKEN", ""))
    jira_personal_token: str = field(
        default_factory=lambda: os.environ.get("JIRA_PERSONAL_TOKEN", "")
    )

    @property
    def jira_enabled(self) -> bool:
        """True only when all three real-Jira credentials are set. Used
        by tools.py to branch between the mocked JSON store and real MCP
        calls — checked at call time (a property, not a frozen field), so
        tests can flip os.environ + reconstruct Config() without
        reimporting this whole module."""
        cloud_credentials = bool(self.jira_username and self.jira_api_token)
        server_credentials = bool(self.jira_personal_token)
        return bool(self.jira_url and (cloud_credentials or server_credentials))

    def require_openai_key(self) -> None:
        if not self.openai_api_key:
            raise MissingAPIKeyError(
                "OPENAI_API_KEY is not configured. This agent requires a real, "
                "working OpenAI key (used for the reasoning model and for "
                "embeddings) — set OPENAI_API_KEY in .env before running. "
                "This repo has no mock mode."
            )


class MissingAPIKeysError(RuntimeError):
    """Raised when INCIDENT_AGENT_API_KEYS is not configured. Mirrors the
    no-silent-degrade policy applied to OPENAI_API_KEY above: an
    unauthenticated backend is not an acceptable default, so a missing
    auth config fails loudly at import time rather than serving every
    request unauthenticated."""


def require_api_keys_configured() -> None:
    if not API_KEYS:
        raise MissingAPIKeysError(
            "INCIDENT_AGENT_API_KEYS is not configured. Set at least one "
            "comma-separated API key in .env before running the backend — "
            "see .env.example. There is no unauthenticated mode."
        )


config = Config()
config.require_openai_key()  # fail immediately at import time if unconfigured

# Ensure data directories exist (does not require an API call).
JIRA_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
INCIDENTS_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
CHECKPOINT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
