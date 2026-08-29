"""Pydantic request/response models for the FastAPI API contract.

Kept separate from route handlers so the contract is easy to cross-check
against the frontend independently of routing/wiring logic.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    session_id: str
    message: str
    user_key: str
    provider: str | None = None
    model: str | None = None
    api_key: str | None = None


class ChatResponse(BaseModel):
    final_answer: str
    stance: Literal["buy", "sell", "hold"] | None = None
    trail_events: list[dict[str, Any]] = Field(default_factory=list)
    memory_note: str | None = None


class NewSessionRequest(BaseModel):
    pass


class NewSessionResponse(BaseModel):
    session_id: str


class TrailResponse(BaseModel):
    trail_events: list[dict[str, Any]] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    tracing_tier: str
