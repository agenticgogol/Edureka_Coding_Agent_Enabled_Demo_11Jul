"""Env loading for the chatbot demo backend.

No mock mode: OPENAI_API_KEY must be set in .env for the default-provider
flow to work. Other provider keys are supplied per-request by the
frontend, not read from env.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


class MissingAPIKeyError(RuntimeError):
    pass


@dataclass(frozen=True)
class Config:
    openai_api_key: str = field(default_factory=lambda: os.environ.get("OPENAI_API_KEY", ""))

    def require_default_key(self) -> None:
        if not self.openai_api_key:
            raise MissingAPIKeyError(
                "OPENAI_API_KEY is not set in .env. This is required for the "
                "default provider flow — there is no mock fallback."
            )


config = Config()
config.require_default_key()
