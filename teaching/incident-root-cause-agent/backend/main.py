"""FastAPI backend for the incident-root-cause-agent teaching demo.

Per `system_design/03_runtime_deployment_shape.md`, exposes exactly two
synchronous legs around the durable human-approval pause, plus a read-only
history leg backed by the shared SQLite `incidents` table:

- POST   /incidents                     -> submit leg (analysis, blocks to a terminal/paused state)
- POST   /incidents/{thread_id}/approve -> approve/reject leg (execution, blocks to a terminal state)
- GET    /incidents                     -> audit history (read-only)
- GET    /incidents/{incident_id}       -> single incident detail (read-only)
- DELETE /incidents?confirm=true        -> irreversibly wipe all incident/ticket/checkpoint history

This module imports ONLY `backend.agent.interface` — never the LangGraph
internals (`graph.py`/`state.py`/`tools.py`) directly, per the agent
module's README. No mock mode: `interface.py` fails loudly at import time
if `OPENAI_API_KEY` is not configured.
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Iterator

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.agent import db
from backend.agent import mcp_github, tools
from backend.agent.config import config
from backend.agent.interface import (
    get_incident_status,
    reset_all_history,
    resume_incident,
    start_incident,
    stream_resume_incident,
    stream_start_incident,
)
from backend.agent.tracing import setup_tracing
from backend.auth import verify_api_key

logger = logging.getLogger("incident_backend")

setup_tracing()  # no-op if PHOENIX_COLLECTOR_ENDPOINT is unset; see tracing.py

app = FastAPI(
    title="Incident Root-Cause Triage Agent API",
    description=(
        "Backend for the incident-root-cause-agent teaching demo. Wraps the "
        "LangGraph bounded-ReAct agent in backend/agent/interface.py."
    ),
    version="1.0.0",
)

# CORS: allow the local Streamlit frontend to call this API during the demo.
# Streamlit's default dev port is 8501; FastAPI's default dev port is 8000.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8501",
        "http://127.0.0.1:8501",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Terminal outcomes as returned by interface.py's `status` field. Any of
# these on a stored incident means it cannot be approved/rejected again.
_TERMINAL_STATUSES = {
    "resolved_infra",
    "resolved_code_fix",
    "rejected",
    "failed_after_retry",
    "escalated",
}


# --- Request/response models ------------------------------------------------


class SubmitIncidentRequest(BaseModel):
    incident_text: str = Field(
        ..., min_length=1, description="Free-form incident description from the user."
    )


class ApproveIncidentRequest(BaseModel):
    approved: bool = Field(..., description="True to approve the drafted patch, False to reject it.")
    rejection_note: str | None = Field(
        default=None, description="Optional note recorded when approved=False."
    )


class MatchedPrecedent(BaseModel):
    """A prior incident precedent_check found similar enough to surface
    (cosine similarity >= INCIDENT_AGENT_PRECEDENT_SIMILARITY_THRESHOLD).
    The agent still independently re-verifies the root cause — this is
    shown to the user as informational context, not a substitute finding."""

    precedent_incident_id: str | None = None
    similarity: float | None = None
    identified_repo: str | None = None
    identified_file: str | None = None
    outcome: str | None = None


class IncidentResponse(BaseModel):
    """Flat public shape returned by both the submit and approve legs.
    Mirrors `interface._public_view` exactly — see that function's field
    set for the authoritative source of truth. Not every field is
    populated on every status (e.g. `diff`/`patch_explanation` are only
    set for `pending_approval`)."""

    thread_id: str
    status: str
    incident_id: str | None = None
    identified_repo: str | None = None
    identified_file: str | None = None
    root_cause: str | None = None
    classification: str | None = None
    ticket_id: str | None = None
    jira_ticket: dict[str, Any] | None = None
    diff: str | None = None
    patch_explanation: str | None = None
    patch_applied: bool | None = None
    test_result: Any | None = None
    message: str | None = None
    matched_precedent: MatchedPrecedent | None = None


class IncidentHistoryItem(BaseModel):
    """One row from the `incidents` audit table."""

    id: str
    created_at: float
    incident_text: str
    identified_repo: str | None = None
    identified_file: str | None = None
    root_cause: str | None = None
    classification: str | None = None
    matched_precedent_id: str | None = None
    drafted_patch_summary: str | None = None
    ticket_id: str | None = None
    approval_status: str | None = None
    test_result: str | None = None
    outcome: str | None = None


class ResetHistoryResponse(BaseModel):
    incidents_deleted: int
    tickets_deleted: int
    checkpoint_threads_deleted: int


class GitHubScanRequest(BaseModel):
    repository: str = Field(..., min_length=3)
    request: str = Field(
        default="Find probable bugs and incident causes across this repository.", min_length=5
    )


class GitHubTicketRequest(BaseModel):
    repository: str
    finding: dict[str, Any]


class GitHubCloseRequest(BaseModel):
    confirmed: bool = Field(..., description="Human confirms the patch was manually applied and pushed/merged.")


# --- Helpers -----------------------------------------------------------------


def _row_to_history_item(row) -> IncidentHistoryItem:
    return IncidentHistoryItem(
        id=row["id"],
        created_at=row["created_at"],
        incident_text=row["incident_text"],
        identified_repo=row["identified_repo"],
        identified_file=row["identified_file"],
        root_cause=row["root_cause"],
        classification=row["classification"],
        matched_precedent_id=row["matched_precedent_id"],
        drafted_patch_summary=row["drafted_patch_summary"],
        ticket_id=row["ticket_id"],
        approval_status=row["approval_status"],
        test_result=row["test_result"],
        outcome=row["outcome"],
    )


def _github_ticket_view(ticket_id: str) -> dict[str, Any] | None:
    ticket = db.get_ticket(ticket_id)
    if not ticket:
        return None
    return {
        **ticket,
        "key": ticket_id,
        "url": f"{config.jira_url}/browse/{ticket_id}" if config.jira_enabled else None,
    }


# --- Routes --------------------------------------------------------------


@app.post("/incidents", response_model=IncidentResponse, dependencies=[Depends(verify_api_key)])
def submit_incident(payload: SubmitIncidentRequest) -> dict[str, Any]:
    """Submit leg. Runs the analysis leg synchronously (precedent check ->
    repo/root-cause search -> classification -> draft, or infra resolution,
    or step-ceiling escalation) and blocks until one of those three
    terminal-or-paused states is reached."""
    try:
        result = start_incident(payload.incident_text)
    except Exception as exc:  # noqa: BLE001 - surface as a clean 500, no leaked internals
        logger.exception("start_incident failed")
        raise HTTPException(status_code=500, detail="Failed to process incident.") from exc
    return result


@app.post("/github/scan", dependencies=[Depends(verify_api_key)])
def scan_github_repository(payload: GitHubScanRequest) -> dict[str, Any]:
    """Explicit user-consented, read-only repository scan through GitHub MCP."""
    try:
        return mcp_github.scan_repository(payload.repository, payload.request)
    except Exception as exc:  # noqa: BLE001
        logger.exception("GitHub repository scan failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/github/tickets", dependencies=[Depends(verify_api_key)])
def create_github_ticket(payload: GitHubTicketRequest) -> dict[str, Any]:
    """Create Jira only after the UI's explicit user confirmation."""
    finding = payload.finding
    ticket_id = str(uuid.uuid4())
    title = str(finding.get("title") or "Probable GitHub repository bug")
    file_path = str(finding.get("file") or "unknown file")
    description = (
        f"GitHub repository: {payload.repository}\n"
        f"File: {file_path}\n"
        f"Severity: {finding.get('severity', 'unknown')}\n\n"
        f"Evidence: {finding.get('evidence', '')}\n\n"
        f"Root cause: {finding.get('root_cause', '')}\n\n"
        "Proposed patch (unified diff):\n"
        f"{finding.get('unified_diff', '')}"
    )
    try:
        ticket = tools.create_jira_ticket(ticket_id, f"[{payload.repository}] {title}", description)
        return {"ticket": _github_ticket_view(ticket["ticket_id"]), "status": "open"}
    except Exception as exc:  # noqa: BLE001
        logger.exception("GitHub Jira ticket creation failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/github/tickets/{ticket_id}/close", dependencies=[Depends(verify_api_key)])
def close_github_ticket(ticket_id: str, payload: GitHubCloseRequest) -> dict[str, Any]:
    if not payload.confirmed:
        raise HTTPException(status_code=400, detail="Human confirmation is required before closing Jira.")
    try:
        ticket = tools.close_jira_ticket(
            ticket_id,
            "Human confirmed the proposed patch was manually applied and pushed/merged.",
        )
        return {"ticket": _github_ticket_view(ticket_id), "status": ticket.get("status", "closed")}
    except Exception as exc:  # noqa: BLE001
        logger.exception("GitHub Jira ticket close failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def _sse_event(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, default=str)}\n\n"


def _sse_wrap(events: Iterator[dict[str, Any]], failure_message: str) -> Iterator[str]:
    """Formats each event as SSE and turns any exception raised mid-stream
    into a final `type: error` event instead of letting it become a
    half-sent HTTP response with no valid status code to change (an SSE
    response's headers/200 are already committed before the first chunk
    is even flushed) — the client must check for `type: error` the same
    way it checks any other event type, not rely on the HTTP status."""
    try:
        for event in events:
            yield _sse_event(event)
    except Exception:  # noqa: BLE001 - reported as a stream event, not a raw 500
        logger.exception(failure_message)
        yield _sse_event({"type": "error", "message": failure_message})


@app.post("/incidents/stream", dependencies=[Depends(verify_api_key)])
def submit_incident_stream(payload: SubmitIncidentRequest) -> StreamingResponse:
    """Streaming equivalent of POST /incidents. Emits
    `data: {"type": "progress", "message": "..."}` events as the analysis
    leg runs, followed by one `data: {"type": "result", ...}` event with
    the exact same payload the blocking route would have returned (or
    `type: error` on failure). Same auth/behavior as the blocking route —
    this is a transport-level alternative, not a different feature."""
    events = stream_start_incident(payload.incident_text)
    return StreamingResponse(
        _sse_wrap(events, "Failed to process incident."),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post(
    "/incidents/{thread_id}/approve/stream",
    dependencies=[Depends(verify_api_key)],
)
def approve_incident_stream(thread_id: str, payload: ApproveIncidentRequest) -> StreamingResponse:
    """Streaming equivalent of POST /incidents/{thread_id}/approve. Same
    404/409 guard as the blocking route (checked before opening the
    stream, so those still arrive as real HTTP status codes — only
    failures during the actual graph run become `type: error` SSE
    events, since by then the 200 + streaming headers are already sent)."""
    _require_approvable_incident(thread_id)
    events = stream_resume_incident(
        thread_id=thread_id, approved=payload.approved, rejection_note=payload.rejection_note
    )
    return StreamingResponse(
        _sse_wrap(events, "Failed to resume incident."),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _require_approvable_incident(thread_id: str) -> None:
    """Shared guard for both the blocking and streaming approve routes —
    raises the same 404/409s either way rather than duplicating (and
    risking drifting) this logic across two route handlers."""
    try:
        current = get_incident_status(thread_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("get_incident_status failed for thread_id=%s", thread_id)
        raise HTTPException(status_code=404, detail="Incident not found.") from exc

    if current.get("status") is None or current.get("status") == "unknown":
        raise HTTPException(status_code=404, detail="Incident not found.")

    if current.get("status") in _TERMINAL_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Incident is already in a terminal state ({current.get('status')}) "
                "and cannot be approved or rejected again."
            ),
        )

    if current.get("status") != "pending_approval":
        raise HTTPException(
            status_code=409,
            detail=f"Incident is not awaiting approval (current status: {current.get('status')}).",
        )


@app.post(
    "/incidents/{thread_id}/approve",
    response_model=IncidentResponse,
    dependencies=[Depends(verify_api_key)],
)
def approve_incident(thread_id: str, payload: ApproveIncidentRequest) -> dict[str, Any]:
    """Approve/reject leg. Resumes the graph from its checkpoint. If
    approved, runs apply_patch -> run_tests -> close_jira_ticket (with the
    one draft_patch retry on test failure) synchronously and blocks until a
    terminal state (or the retry's re-entered pending_approval) is
    reached."""
    _require_approvable_incident(thread_id)
    try:
        result = resume_incident(
            thread_id=thread_id,
            approved=payload.approved,
            rejection_note=payload.rejection_note,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("resume_incident failed for thread_id=%s", thread_id)
        raise HTTPException(status_code=500, detail="Failed to resume incident.") from exc
    return result


@app.get(
    "/incidents", response_model=list[IncidentHistoryItem], dependencies=[Depends(verify_api_key)]
)
def list_incidents() -> list[IncidentHistoryItem]:
    """Read-only audit history, most recent first."""
    rows = db.all_incidents()
    return [_row_to_history_item(row) for row in rows]


@app.get(
    "/incidents/{incident_id}",
    response_model=IncidentHistoryItem,
    dependencies=[Depends(verify_api_key)],
)
def get_incident_detail(incident_id: str) -> IncidentHistoryItem:
    """Read-only single incident lookup by incident_id (the `incidents`
    table primary key — distinct from `thread_id`, the checkpointer key
    used by the approve leg)."""
    row = db.get_incident(incident_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Incident not found.")
    return _row_to_history_item(row)


@app.delete(
    "/incidents",
    response_model=ResetHistoryResponse,
    dependencies=[Depends(verify_api_key)],
)
def reset_history(confirm: bool = False) -> dict[str, int]:
    """Irreversibly wipes ALL incident audit records, mocked Jira tickets,
    and LangGraph checkpoint state — used by the UI's 'Reset history'
    action. Requires `?confirm=true` explicitly; a bare DELETE (no query
    param, or confirm=false) is rejected with 400 rather than silently
    treated as a no-op, so an accidental request without the param fails
    loudly instead of doing nothing without saying why. Auth-protected
    like every other mutating route — this is NOT an additional
    authorization tier, just an extra explicit-intent guard on top of it."""
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="This permanently deletes all incident history. Retry with ?confirm=true.",
        )
    logger.warning("reset_history invoked — wiping all incident/ticket/checkpoint data")
    return reset_all_history()


@app.get("/health")
def health() -> dict[str, Any]:
    """Deliberately unauthenticated (container/orchestrator health checks
    shouldn't need a key) but actually verifies the DB is reachable,
    rather than returning a static payload regardless of real backend
    health."""
    try:
        db.all_incidents()
        db_ok = True
    except Exception:  # noqa: BLE001 - health check must never raise
        db_ok = False
    return {"status": "ok" if db_ok else "degraded", "db": "ok" if db_ok else "unreachable"}
