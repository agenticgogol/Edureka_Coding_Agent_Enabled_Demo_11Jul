"""Route handlers for the stock-research-debate-assistant FastAPI backend.

Thin HTTP layer only: session-state bookkeeping (in-process dict, per this
teaching demo's scope) and delegating all agent/graph logic to
`backend.agent.run_turn`. No graph-building or LangGraph logic lives here.
"""
from __future__ import annotations

import uuid
import threading

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
_JOBS: dict[str, dict] = {}


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


def _run_chat_job(job_id: str, payload: ChatRequest) -> None:
    job = _JOBS[job_id]
    try:
        previous_state = _SESSIONS.get(payload.session_id)
        result = run_turn(
            previous_state,
            payload.message,
            user_key=payload.user_key,
            provider=payload.provider,
            model=payload.model,
            api_key=payload.api_key,
            progress_callback=lambda event: job["events"].append(event),
        )
        _SESSIONS[payload.session_id] = result["session_state"]
        job["response"] = {
            "final_answer": result.get("final_answer", ""),
            "stance": result.get("stance").lower() if isinstance(result.get("stance"), str) else None,
            "trail_events": result.get("new_trail_events", []),
            "memory_note": result.get("memory_note"),
        }
        job["status"] = "complete"
    except Exception as exc:  # noqa: BLE001
        job["error"] = str(exc)
        job["status"] = "error"


@router.post("/chat/start")
def start_chat(payload: ChatRequest) -> dict:
    job_id = str(uuid.uuid4())
    _JOBS[job_id] = {"status": "running", "events": [], "response": None, "error": None}
    thread = threading.Thread(target=_run_chat_job, args=(job_id, payload), daemon=True)
    thread.start()
    return {"job_id": job_id}


@router.get("/chat/jobs/{job_id}")
def chat_job_status(job_id: str) -> dict:
    job = _JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Unknown job_id '{job_id}'.")
    return {
        "status": job["status"],
        "events": list(job["events"]),
        "response": job["response"],
        "error": job["error"],
    }
