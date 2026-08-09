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
JIRA_STORE_PATH = DATA_DIR / "jira" / "tickets.json"
INCIDENTS_DB_PATH = DATA_DIR / "db" / "incidents.sqlite"
CHECKPOINT_DB_PATH = DATA_DIR / "db" / "checkpoints.sqlite"

REASONING_MODEL = os.environ.get("INCIDENT_AGENT_MODEL", "gpt-4o-mini")
EMBEDDING_MODEL = os.environ.get("INCIDENT_AGENT_EMBEDDING_MODEL", "text-embedding-3-small")

ALLOWED_REPOS = ("checkout-service", "auth-service", "notifications-service")


@dataclass(frozen=True)
class Config:
    openai_api_key: str = field(default_factory=lambda: os.environ.get("OPENAI_API_KEY", ""))

    phoenix_collector_endpoint: str = field(
        default_factory=lambda: os.environ.get("PHOENIX_COLLECTOR_ENDPOINT", "")
    )
    phoenix_api_key: str = field(default_factory=lambda: os.environ.get("PHOENIX_API_KEY", ""))

    def require_openai_key(self) -> None:
        if not self.openai_api_key:
            raise MissingAPIKeyError(
                "OPENAI_API_KEY is not configured. This agent requires a real, "
                "working OpenAI key (used for the reasoning model and for "
                "embeddings) — set OPENAI_API_KEY in .env before running. "
                "This repo has no mock mode."
            )


config = Config()
config.require_openai_key()  # fail immediately at import time if unconfigured

# Ensure data directories exist (does not require an API call).
(DATA_DIR / "jira").mkdir(parents=True, exist_ok=True)
(DATA_DIR / "db").mkdir(parents=True, exist_ok=True)
