"""Config/env loading for the stock-research-debate-assistant agent module.

Adapted from `_shared/config.py` per this repo's helper-utils convention
(copy-per-project, then add project-specific vars). No mock mode: a missing
LLM key fails loudly at import time, never falls back to canned output.
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

    tavily_api_key: str = field(default_factory=lambda: os.environ.get("TAVILY_API_KEY", ""))

    phoenix_collector_endpoint: str = field(
        default_factory=lambda: os.environ.get("PHOENIX_COLLECTOR_ENDPOINT", "")
    )
    phoenix_api_key: str = field(default_factory=lambda: os.environ.get("PHOENIX_API_KEY", ""))

    memory_db_path: str = field(
        default_factory=lambda: os.environ.get(
            "STOCK_AGENT_MEMORY_DB",
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "memory.db"),
        )
    )

    @property
    def has_any_llm_key(self) -> bool:
        return bool(self.anthropic_api_key or self.openai_api_key or self.groq_api_key)

    def require_llm_key(self) -> None:
        """Call at startup (require-api-key skill). Raises immediately if no
        key is set — never continue with degraded behavior."""
        if not self.has_any_llm_key:
            raise MissingAPIKeyError(
                "No LLM API key configured. Set one of ANTHROPIC_API_KEY, "
                "OPENAI_API_KEY, or GROQ_API_KEY in .env before running. "
                "This project has no mock mode — it requires a real, "
                "working key."
            )

    def require_tavily_key(self) -> None:
        if not self.tavily_api_key:
            raise MissingAPIKeyError(
                "TAVILY_API_KEY is not configured. The news-search tool "
                "(tavily-mcp) requires a free Tavily API key in .env."
            )


config = Config()
config.require_llm_key()  # fail immediately at import time if unconfigured

DEFAULT_ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_GROQ_MODEL = "llama-3.1-70b-versatile"
