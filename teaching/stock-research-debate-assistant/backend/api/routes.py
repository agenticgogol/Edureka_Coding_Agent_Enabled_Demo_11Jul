"""Route handlers for the stock-research-debate-assistant FastAPI backend.

Thin HTTP layer only: session-state bookkeeping (in-process dict, per this
teaching demo's scope) and delegating all agent/graph logic to
`backend.agent.run_turn`. No graph-building or LangGraph logic lives here.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException

from backend.agent import run_turn
from backend.api.schemas import (
    ChatRequest,
    ChatResponse,
    HealthResponse,
    NewSessionResponse,
    TrailResponse,
)
from backend.observability import active_tier, traced_chat_call

router = APIRouter()

# In-process session-state store: session_id -> opaque state dict returned
# by `run_turn`. Per the teaching brief's scope, no Redis/durable storage —
# state is lost on process restart, which is fine for a demo.
_SESSIONS: dict[str, dict] = {}


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(tracing_tier=active_tier())


@router.post("/session/new", response_model=NewSessionResponse)
def new_session() -> NewSessionResponse:
    session_id = str(uuid.uuid4())
    _SESSIONS[session_id] = None  # None => run_turn starts a fresh session
    return NewSessionResponse(session_id=session_id)


@router.get("/session/{session_id}/trail", response_model=TrailResponse)
def get_trail(session_id: str) -> TrailResponse:
    if session_id not in _SESSIONS:
        raise HTTPException(status_code=404, detail=f"Unknown session_id '{session_id}'.")
    state = _SESSIONS[session_id] or {}
    return TrailResponse(trail_events=state.get("trail", []))


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    # Auto-register unseen session_ids rather than 404ing, so a frontend
    # that generates its own session_id (rather than calling /session/new
    # first) still works.
    previous_state = _SESSIONS.get(payload.session_id)

    with traced_chat_call(payload.session_id, payload.message) as span:
        result = run_turn(
            previous_state,
            payload.message,
            user_key=payload.user_key,
            provider=payload.provider,
            model=payload.model,
            api_key=payload.api_key,
        )
        span["trail_events"] = result.get("new_trail_events", [])
        span["stance"] = result.get("stance")
        span["final_answer"] = result.get("final_answer", "")

    _SESSIONS[payload.session_id] = result["session_state"]

    stance = result.get("stance")
    return ChatResponse(
        final_answer=result.get("final_answer", ""),
        stance=stance.lower() if isinstance(stance, str) else None,
        trail_events=result.get("new_trail_events", []),
        memory_note=result.get("memory_note"),
    )
