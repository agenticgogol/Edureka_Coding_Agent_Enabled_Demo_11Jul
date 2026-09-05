"""Route handlers for the stock-research-debate-assistant FastAPI backend.

Thin HTTP layer only: session-state bookkeeping (in-process dict, per this
teaching demo's scope), auth-token resolution, and delegating all
agent/graph logic to `backend.agent.run_turn`. No graph-building or
LangGraph logic lives here.

Auth: every `/chat*` and `/session/*` endpoint (except `/session/new`,
which just mints an opaque conversation id) requires a valid
`X-Session-Token` header, issued by `POST /auth/session` and resolved to a
server-known `user_key` via `backend.agent.memory.resolve_user_key`. There
is no free-text `user_key` accepted from the client anywhere in this
module anymore — an unknown/missing token is a hard 401, not a soft
fallback identity.

Streaming: `POST /chat/stream` is the real-time path — it streams
Server-Sent Events (trail-progress events as the LangGraph run progresses,
then one final `ChatResponse`-shaped event) as the turn actually executes,
via a background thread + queue bridging `run_turn`'s synchronous
`progress_callback` into the async generator FastAPI streams out.
`/chat` (single blocking response) and `/chat/start` + `/chat/jobs/{id}`
(background job + poll) are both kept for backward compatibility — some
callers/tests prefer a plain synchronous or poll-based contract over SSE.
"""
from __future__ import annotations

import collections
import json
import queue
import time
import uuid
import threading

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import StreamingResponse

from backend.agent import memory, run_turn
from backend.agent.tools.price_fundamentals import check_ticker_exists
from backend.api.schemas import (
    ChatRequest,
    ChatResponse,
    HealthResponse,
    NewSessionResponse,
    SessionHistoryResponse,
    SessionTokenResponse,
    TickerValidateResponse,
    TrailResponse,
)
from backend.observability import active_tier, traced_chat_call

router = APIRouter()

# In-process session-state store: session_id -> opaque state dict returned
# by `run_turn`. Per the teaching brief's scope, no Redis/durable storage —
# state is lost on process restart, which is fine for a demo.
_SESSIONS: dict[str, dict] = {}

# session_id -> list of full ChatResponse-shaped dicts, one per turn, in
# chronological order. Distinct from `_SESSIONS` (which holds the opaque
# graph state used to resume the *next* turn) — this is purely additive
# history for `/session/{id}/turns` so a frontend reload can reconstruct
# exact turn boundaries instead of only a flattened trail-event log.
_SESSION_TURNS: dict[str, list[dict]] = collections.defaultdict(list)
_SESSION_TURNS_LOCK = threading.Lock()

# job_id -> job dict, plus a "created_at" timestamp (epoch seconds) used to
# evict stale/completed jobs so this in-process dict doesn't grow
# unbounded across a long-running demo session (background /chat/start
# polling jobs). Jobs older than _JOB_TTL_SECONDS are purged lazily on
# every job-store access rather than via a separate sweeper thread, which
# keeps this teaching-demo backend dependency-free.
_JOBS: dict[str, dict] = {}
_JOB_TTL_SECONDS = 30 * 60  # purge jobs 30+ minutes old
_JOB_LOCK = threading.Lock()

# job_id -> threading.Event, for /chat/stream turns only (client sends a
# uuid4 job_id in ChatRequest). Setting the event signals run_turn's
# graph.stream() loop to stop at the next node boundary. Registered when
# the worker thread starts, removed in a finally block when the turn ends
# (success, error, or cancellation) -- same cleanup discipline as
# _purge_stale_jobs. Reuses _JOB_LOCK since it's the same kind of
# short-held in-process dict guard, no need for a second lock.
_CANCEL_EVENTS: dict[str, threading.Event] = {}

# Basic in-memory rate limiting per user_key on /chat, /chat/start, and
# /chat/stream, to bound runaway real-LLM-API spend from a single client
# hammering the endpoint. Sliding window: at most _RATE_LIMIT_MAX_REQUESTS
# per _RATE_LIMIT_WINDOW_SECONDS per user_key.
_RATE_LIMIT_WINDOW_SECONDS = 60
_RATE_LIMIT_MAX_REQUESTS = 10
_RATE_LIMIT_HISTORY: dict[str, collections.deque] = collections.defaultdict(collections.deque)
_RATE_LIMIT_LOCK = threading.Lock()

# Separate, per-IP limit on POST /auth/session itself — that endpoint is
# unauthenticated by necessity (it's how a client gets its first token), so
# without this an IP could mint unlimited fresh tokens to dodge the
# per-user_key /chat* rate limit above entirely.
_AUTH_RATE_LIMIT_WINDOW_SECONDS = 60
_AUTH_RATE_LIMIT_MAX_REQUESTS = 5
_AUTH_RATE_LIMIT_HISTORY: dict[str, collections.deque] = collections.defaultdict(collections.deque)
_AUTH_RATE_LIMIT_LOCK = threading.Lock()


def _purge_stale_jobs() -> None:
    cutoff = time.time() - _JOB_TTL_SECONDS
    with _JOB_LOCK:
        stale_ids = [job_id for job_id, job in _JOBS.items() if job.get("created_at", 0) < cutoff]
        for job_id in stale_ids:
            del _JOBS[job_id]


def _enforce_rate_limit(user_key: str) -> None:
    now = time.time()
    with _RATE_LIMIT_LOCK:
        history = _RATE_LIMIT_HISTORY[user_key]
        while history and now - history[0] > _RATE_LIMIT_WINDOW_SECONDS:
            history.popleft()
        if len(history) >= _RATE_LIMIT_MAX_REQUESTS:
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Rate limit exceeded: max {_RATE_LIMIT_MAX_REQUESTS} requests per "
                    f"{_RATE_LIMIT_WINDOW_SECONDS}s per user_key. Try again shortly."
                ),
            )
        history.append(now)


def _require_client_key(payload: ChatRequest) -> None:
    """Public deployment guard: every real LLM call must be paid for by the
    caller's own key, never the server's `.env` default. `.env` keys stay
    reserved for local/admin use (e.g. `llm_client.verify_key`, run outside
    these HTTP routes). Without this, an anonymous visitor omitting
    `provider`/`api_key` would silently ride the server's key for free."""
    if not payload.provider or not payload.api_key:
        raise HTTPException(
            status_code=400,
            detail="This is a public demo — provide your own 'provider' and 'api_key' "
            "in the request (the Streamlit sidebar's API key field). The server's "
            "own .env keys are not used for chat requests.",
        )


def _enforce_auth_rate_limit(client_ip: str) -> None:
    now = time.time()
    with _AUTH_RATE_LIMIT_LOCK:
        history = _AUTH_RATE_LIMIT_HISTORY[client_ip]
        while history and now - history[0] > _AUTH_RATE_LIMIT_WINDOW_SECONDS:
            history.popleft()
        if len(history) >= _AUTH_RATE_LIMIT_MAX_REQUESTS:
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Rate limit exceeded: max {_AUTH_RATE_LIMIT_MAX_REQUESTS} new sessions "
                    f"per {_AUTH_RATE_LIMIT_WINDOW_SECONDS}s per IP. Try again shortly."
                ),
            )
        history.append(now)


def _authenticate(x_session_token: str | None) -> str:
    """Resolves the `X-Session-Token` header to a server-known `user_key`.

    Raises 401 for a missing or unknown token — there is no fallback
    identity. Callers must obtain a token from `POST /auth/session` first.
    """
    if not x_session_token:
        raise HTTPException(status_code=401, detail="Missing X-Session-Token header. Call POST /auth/session first.")
    user_key = memory.resolve_user_key(x_session_token)
    if user_key is None:
        raise HTTPException(status_code=401, detail="Unknown or expired session token.")
    return user_key


def _record_turn(session_id: str, response: ChatResponse) -> None:
    with _SESSION_TURNS_LOCK:
        _SESSION_TURNS[session_id].append(response.model_dump())


def _build_chat_response(result: dict, usage: list[dict] | None = None) -> ChatResponse:
    stance = result.get("stance")
    return ChatResponse(
        final_answer=result.get("final_answer", ""),
        stance=stance.lower() if isinstance(stance, str) else None,
        confidence=result.get("confidence"),
        trail_events=result.get("new_trail_events", []),
        memory_note=result.get("memory_note"),
        risk_tolerance=result.get("risk_tolerance"),
        usage=usage or [],
    )


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(tracing_tier=active_tier())


@router.post("/auth/session", response_model=SessionTokenResponse)
def create_auth_session(request: Request) -> SessionTokenResponse:
    """Issues a new server-side session credential: an unguessable random
    token mapped to a fresh random `user_key`. The client stores the token
    and sends it back on `X-Session-Token` for every subsequent chat/
    session request — free-text `user_key` is no longer accepted.

    Rate-limited per IP (see `_enforce_auth_rate_limit`) since this is the
    one endpoint with no prior auth — unlimited, it would let a client mint
    a fresh token per request to dodge the per-user_key /chat* rate limit."""
    _enforce_auth_rate_limit(request.client.host if request.client else "unknown")
    token, user_key = memory.create_session()
    return SessionTokenResponse(token=token, user_key=user_key)


@router.post("/session/new", response_model=NewSessionResponse)
def new_session() -> NewSessionResponse:
    session_id = str(uuid.uuid4())
    _SESSIONS[session_id] = None  # None => run_turn starts a fresh session
    return NewSessionResponse(session_id=session_id)


@router.get("/session/{session_id}/trail", response_model=TrailResponse)
def get_trail(session_id: str, x_session_token: str | None = Header(default=None)) -> TrailResponse:
    _authenticate(x_session_token)
    if session_id not in _SESSIONS:
        raise HTTPException(status_code=404, detail=f"Unknown session_id '{session_id}'.")
    state = _SESSIONS[session_id] or {}
    return TrailResponse(trail_events=state.get("trail", []))


@router.get("/session/{session_id}/turns", response_model=SessionHistoryResponse)
def get_session_turns(session_id: str, x_session_token: str | None = Header(default=None)) -> SessionHistoryResponse:
    """Full per-turn history for a session: the exact `ChatResponse` shape
    (final_answer, stance, confidence, usage, etc.) for every turn so far,
    in order — lets a frontend reload reconstruct exact turn boundaries
    instead of only replaying the flat trail-event log."""
    _authenticate(x_session_token)
    if session_id not in _SESSIONS:
        raise HTTPException(status_code=404, detail=f"Unknown session_id '{session_id}'.")
    with _SESSION_TURNS_LOCK:
        turns = list(_SESSION_TURNS.get(session_id, []))
    return SessionHistoryResponse(turns=turns)


@router.get("/tickers/validate", response_model=TickerValidateResponse)
def validate_ticker(symbol: str) -> TickerValidateResponse:
    """Cheap, non-LLM ticker-existence check (a lightweight yfinance
    lookup) so the frontend can reject an obviously-bad ticker before
    spending a full paid `/chat` turn on it. No auth required — it's a
    read-only public-data lookup with no cost/identity implications."""
    result = check_ticker_exists(symbol)
    return TickerValidateResponse(**result)


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, x_session_token: str | None = Header(default=None)) -> ChatResponse:
    user_key = _authenticate(x_session_token)
    _require_client_key(payload)
    _enforce_rate_limit(user_key)
    # Auto-register unseen session_ids rather than 404ing, so a frontend
    # that generates its own session_id (rather than calling /session/new
    # first) still works.
    previous_state = _SESSIONS.get(payload.session_id)

    with traced_chat_call(payload.session_id, payload.message) as span:
        result = run_turn(
            previous_state,
            payload.message,
            user_key=user_key,
            provider=payload.provider,
            model=payload.model,
            api_key=payload.api_key,
        )
        span["trail_events"] = result.get("new_trail_events", [])
        span["stance"] = result.get("stance")
        span["final_answer"] = result.get("final_answer", "")

    _SESSIONS[payload.session_id] = result["session_state"]

    response = _build_chat_response(result, span.get("usage"))
    _record_turn(payload.session_id, response)
    return response


def _run_chat_job(job_id: str, payload: ChatRequest, user_key: str) -> None:
    job = _JOBS[job_id]
    try:
        previous_state = _SESSIONS.get(payload.session_id)
        with traced_chat_call(payload.session_id, payload.message) as span:
            result = run_turn(
                previous_state,
                payload.message,
                user_key=user_key,
                provider=payload.provider,
                model=payload.model,
                api_key=payload.api_key,
                progress_callback=lambda event: job["events"].append(event),
            )
            span["trail_events"] = result.get("new_trail_events", [])
            span["stance"] = result.get("stance")
            span["final_answer"] = result.get("final_answer", "")
        _SESSIONS[payload.session_id] = result["session_state"]
        response = _build_chat_response(result, span.get("usage"))
        _record_turn(payload.session_id, response)
        job["response"] = response.model_dump()
        job["status"] = "complete"
    except Exception as exc:  # noqa: BLE001
        job["error"] = str(exc)
        job["status"] = "error"


@router.post("/chat/start")
def start_chat(payload: ChatRequest, x_session_token: str | None = Header(default=None)) -> dict:
    user_key = _authenticate(x_session_token)
    _require_client_key(payload)
    _enforce_rate_limit(user_key)
    _purge_stale_jobs()
    job_id = str(uuid.uuid4())
    with _JOB_LOCK:
        _JOBS[job_id] = {
            "status": "running",
            "events": [],
            "response": None,
            "error": None,
            "created_at": time.time(),
        }
    thread = threading.Thread(target=_run_chat_job, args=(job_id, payload, user_key), daemon=True)
    thread.start()
    return {"job_id": job_id}


@router.get("/chat/jobs/{job_id}")
def chat_job_status(job_id: str) -> dict:
    _purge_stale_jobs()
    job = _JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Unknown job_id '{job_id}'.")
    return {
        "status": job["status"],
        "events": list(job["events"]),
        "response": job["response"],
        "error": job["error"],
    }


def _stream_chat_events(payload: ChatRequest, user_key: str):
    """Generator driving real SSE: `run_turn` runs on a background thread
    (it's synchronous end-to-end), and its `progress_callback` pushes each
    trail event onto a queue as the LangGraph run actually reaches that
    node — this generator drains the queue and yields an SSE `data:` line
    per event the moment it arrives, instead of the old `/chat/jobs`
    polling contract's post-hoc drip reveal.

    Event shapes yielded (each one JSON-encoded on a `data:` line):
      {"type": "trail_event", "data": {step, ticker, status, detail}}
      {"type": "final", "data": <ChatResponse dict>}
      {"type": "cancelled", "data": <partial ChatResponse dict>}
      {"type": "error", "data": "<error message>"}
    followed by a terminal `event: done` line either way.

    If `payload.job_id` is set, a threading.Event is registered under it in
    `_CANCEL_EVENTS` so `POST /chat/cancel/{job_id}` can signal this turn to
    stop at the next LangGraph node boundary (see `run_turn`'s cancel_event
    param) -- not mid-token-generation, an in-flight LLM call can't be
    aborted cleanly through LangGraph's execution model.
    """
    event_queue: "queue.Queue[dict | None]" = queue.Queue()
    outcome: dict = {}

    cancel_event: threading.Event | None = None
    if payload.job_id:
        cancel_event = threading.Event()
        with _JOB_LOCK:
            _CANCEL_EVENTS[payload.job_id] = cancel_event

    def progress_callback(event: dict) -> None:
        event_queue.put({"type": "trail_event", "data": event})

    def worker() -> None:
        try:
            previous_state = _SESSIONS.get(payload.session_id)
            with traced_chat_call(payload.session_id, payload.message) as span:
                result = run_turn(
                    previous_state,
                    payload.message,
                    user_key=user_key,
                    provider=payload.provider,
                    model=payload.model,
                    api_key=payload.api_key,
                    progress_callback=progress_callback,
                    cancel_event=cancel_event,
                )
                span["trail_events"] = result.get("new_trail_events", [])
                span["stance"] = result.get("stance")
                span["final_answer"] = result.get("final_answer", "")
            _SESSIONS[payload.session_id] = result["session_state"]
            response = _build_chat_response(result, span.get("usage"))
            _record_turn(payload.session_id, response)
            outcome["response"] = response
            outcome["cancelled"] = result.get("cancelled", False)
        except Exception as exc:  # noqa: BLE001
            outcome["error"] = str(exc)
        finally:
            if payload.job_id:
                with _JOB_LOCK:
                    _CANCEL_EVENTS.pop(payload.job_id, None)
            event_queue.put(None)  # sentinel: no more trail events

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

    while True:
        item = event_queue.get()
        if item is None:
            break
        yield f"data: {json.dumps(item, default=str)}\n\n"

    if "error" in outcome:
        yield f"data: {json.dumps({'type': 'error', 'data': outcome['error']}, default=str)}\n\n"
    else:
        response = outcome["response"]
        event_type = "cancelled" if outcome.get("cancelled") else "final"
        yield f"data: {json.dumps({'type': event_type, 'data': response.model_dump()}, default=str)}\n\n"
    yield "event: done\ndata: {}\n\n"


@router.post("/chat/cancel/{job_id}", status_code=202)
def cancel_chat(job_id: str) -> dict:
    """Signals an in-flight `/chat/stream` turn to stop at the next
    LangGraph node boundary. Not a hard error if the job is unknown/already
    finished -- that's an expected race (e.g. user clicks stop just as the
    turn was already completing)."""
    with _JOB_LOCK:
        event = _CANCEL_EVENTS.get(job_id)
        if event is None:
            raise HTTPException(status_code=404, detail="job not found or already finished")
        event.set()
    return {"status": "cancelling", "job_id": job_id}


@router.post("/chat/stream")
def chat_stream(payload: ChatRequest, x_session_token: str | None = Header(default=None)) -> StreamingResponse:
    user_key = _authenticate(x_session_token)
    _require_client_key(payload)
    _enforce_rate_limit(user_key)
    return StreamingResponse(
        _stream_chat_events(payload, user_key),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
