"""Env loading for the full end-to-end RAG demo backend.

No mock mode: OPENAI_API_KEY, QDRANT_URL, and QDRANT_API_KEY must all be
set (in the repo-root .env, or a project-level .env if present) for any
of the pipeline to work. COHERE_API_KEY is optional and only required if
the caller selects the "cohere" embedding option. PHOENIX_COLLECTOR_ENDPOINT
is optional; see observability.py for the fallback chain when it's unset.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    from dotenv import load_dotenv

    # Load project-level .env first (if it exists), then fall back to
    # repo-root .env without overriding already-set values.
    _project_env = Path(__file__).resolve().parent.parent / ".env"
    if _project_env.exists():
        load_dotenv(_project_env)
    load_dotenv()  # repo-root .env (or cwd .env), does not override existing vars
except ImportError:
    pass


class MissingAPIKeyError(RuntimeError):
    pass


@dataclass(frozen=True)
class Config:
    openai_api_key: str = field(default_factory=lambda: os.environ.get("OPENAI_API_KEY", ""))
    qdrant_url: str = field(default_factory=lambda: os.environ.get("QDRANT_URL", ""))
    qdrant_api_key: str = field(default_factory=lambda: os.environ.get("QDRANT_API_KEY", ""))
    cohere_api_key: str = field(default_factory=lambda: os.environ.get("COHERE_API_KEY", ""))
    phoenix_collector_endpoint: str = field(
        default_factory=lambda: os.environ.get("PHOENIX_COLLECTOR_ENDPOINT", "")
    )
    phoenix_api_key: str = field(default_factory=lambda: os.environ.get("PHOENIX_API_KEY", ""))

    def require_required_keys(self) -> None:
        missing = []
        if not self.openai_api_key:
            missing.append("OPENAI_API_KEY")
        if not self.qdrant_url:
            missing.append("QDRANT_URL")
        if not self.qdrant_api_key:
            missing.append("QDRANT_API_KEY")
        if missing:
            raise MissingAPIKeyError(
                f"Missing required env var(s): {', '.join(missing)}. "
                "These are required for the RAG pipeline — there is no mock fallback."
            )

    def require_cohere_key(self) -> None:
        if not self.cohere_api_key:
            raise MissingAPIKeyError(
                "COHERE_API_KEY is not set — required when embedding='cohere' is selected."
            )


config = Config()
config.require_required_keys()
