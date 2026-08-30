"""Pydantic request/response models for the FastAPI API contract.

Kept separate from route handlers so the contract is easy to cross-check
against the frontend independently of routing/wiring logic.

Auth note: `user_key` is never accepted as client-typed free text anymore.
A client first calls `POST /auth/session` to get a server-issued `token`
(mapped server-side to a random `user_key`), then sends that token back on
every subsequent request via the `X-Session-Token` header. See
`api/routes.py`'s `_authenticate` for enforcement.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    session_id: str
    message: str
    provider: str | None = None
    model: str | None = None
    api_key: str | None = None
    # Client-generated (uuid4) id used only by /chat/stream to register a
    # cancel event under; POST /chat/cancel/{job_id} sets it. Optional so
    # /chat and /chat/start (which don't support cancellation) are unaffected.
    job_id: str | None = None


class UsageEntry(BaseModel):
    """One real LLM call's cost/token footprint, in the order calls
    happened during this turn. Populated from `backend/observability.py`'s
    `record_llm_usage`, which `agent/llm_client.py` calls right after every
    real provider response."""

    node: str | None = None
    provider: str
    model: str
    tokens_in: int
    tokens_out: int
    latency_seconds: float
    estimated_cost_usd: float


class ChatResponse(BaseModel):
    final_answer: str
    stance: Literal["buy", "sell", "hold"] | None = None
    confidence: float | None = None
    trail_events: list[dict[str, Any]] = Field(default_factory=list)
    memory_note: str | None = None
    risk_tolerance: str | None = None
    usage: list[UsageEntry] = Field(default_factory=list)


class NewSessionRequest(BaseModel):
    pass


class NewSessionResponse(BaseModel):
    session_id: str


class TrailResponse(BaseModel):
    trail_events: list[dict[str, Any]] = Field(default_factory=list)


class SessionHistoryResponse(BaseModel):
    """Full per-turn chat history for a session — each entry is the exact
    `ChatResponse` returned for that turn, in chronological order, so a
    frontend reload can reconstruct exact turn boundaries instead of only
    a flattened trail-event log (see `TrailResponse`, which stays for
    backward compat / the reasoning-trail view)."""

    turns: list[ChatResponse] = Field(default_factory=list)


class SessionTokenResponse(BaseModel):
    """Response from `POST /auth/session`. `token` must be sent back on the
    `X-Session-Token` header for every `/chat*` and `/session/*` request.
    `user_key` is informational only (e.g. for debugging/display) — the
    server resolves it from the token itself on every authenticated call,
    it is never accepted back from the client as an input."""

    token: str
    user_key: str


class TickerValidateResponse(BaseModel):
    symbol: str
    valid: bool
    detail: str | None = None


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    tracing_tier: str
