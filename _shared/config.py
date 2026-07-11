"""Shared config/env loading template — copied per-project by helper-utils.

No mock mode. If no real LLM key is configured, code using this config
must fail loudly and immediately with a clear message telling the user
which env var to set — never fall back to canned output.

Copy this file into the project (e.g. backend/config.py), then add any
project-specific env vars listed in that project's design.md. Do not
import this file across project boundaries at runtime.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass  # dotenv is optional; env vars can also come from the shell/host


class MissingAPIKeyError(RuntimeError):
    """Raised when no LLM provider key is configured. There is no mock
    fallback in this repo — this must stop execution, not be caught and
    papered over."""


@dataclass(frozen=True)
class Config:
    anthropic_api_key: str = field(default_factory=lambda: os.environ.get("ANTHROPIC_API_KEY", ""))
    openai_api_key: str = field(default_factory=lambda: os.environ.get("OPENAI_API_KEY", ""))
    groq_api_key: str = field(default_factory=lambda: os.environ.get("GROQ_API_KEY", ""))

    qdrant_url: str = field(default_factory=lambda: os.environ.get("QDRANT_URL", ""))
    qdrant_api_key: str = field(default_factory=lambda: os.environ.get("QDRANT_API_KEY", ""))

    supabase_url: str = field(default_factory=lambda: os.environ.get("SUPABASE_URL", ""))
    supabase_service_role_key: str = field(
        default_factory=lambda: os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    )

    phoenix_collector_endpoint: str = field(
        default_factory=lambda: os.environ.get("PHOENIX_COLLECTOR_ENDPOINT", "")
    )
    phoenix_api_key: str = field(default_factory=lambda: os.environ.get("PHOENIX_API_KEY", ""))

    @property
    def has_any_llm_key(self) -> bool:
        return bool(self.anthropic_api_key or self.openai_api_key or self.groq_api_key)

    def require_llm_key(self) -> None:
        """Call this at startup (see require-api-key skill). Raises
        immediately with a clear message if no key is set — do not catch
        this and continue with degraded behavior."""
        if not self.has_any_llm_key:
            raise MissingAPIKeyError(
                "No LLM API key configured. Set one of ANTHROPIC_API_KEY, "
                "OPENAI_API_KEY, or GROQ_API_KEY in .env before running. "
                "This project has no mock mode — it requires a real, "
                "working key."
            )


config = Config()
config.require_llm_key()  # fail immediately at import time if unconfigured
