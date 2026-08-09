"""FastAPI backend for the incident-root-cause-agent teaching demo.

Per `system_design/03_runtime_deployment_shape.md`, exposes exactly two
synchronous legs around the durable human-approval pause, plus a read-only
history leg backed by the shared SQLite `incidents` table:

- POST /incidents                     -> submit leg (analysis, blocks to a terminal/paused state)
- POST /incidents/{thread_id}/approve -> approve/reject leg (execution, blocks to a terminal state)
- GET  /incidents                     -> audit history (read-only)
- GET  /incidents/{incident_id}       -> single incident detail (read-only)

This module imports ONLY `backend.agent.interface` — never the LangGraph
internals (`graph.py`/`state.py`/`tools.py`) directly, per the agent
module's README. No mock mode: `interface.py` fails loudly at import time
if `OPENAI_API_KEY` is not configured.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.agent import db
from backend.agent.interface import get_incident_status, resume_incident, start_incident

logger = logging.getLogger("incident_backend")

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
    diff: str | None = None
    patch_explanation: str | None = None
    test_result: Any | None = None
    message: str | None = None


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


# --- Routes --------------------------------------------------------------


@app.post("/incidents", response_model=IncidentResponse)
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


@app.post("/incidents/{thread_id}/approve", response_model=IncidentResponse)
def approve_incident(thread_id: str, payload: ApproveIncidentRequest) -> dict[str, Any]:
    """Approve/reject leg. Resumes the graph from its checkpoint. If
    approved, runs apply_patch -> run_tests -> close_jira_ticket (with the
    one draft_patch retry on test failure) synchronously and blocks until a
    terminal state (or the retry's re-entered pending_approval) is
    reached."""
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


@app.get("/incidents", response_model=list[IncidentHistoryItem])
def list_incidents() -> list[IncidentHistoryItem]:
    """Read-only audit history, most recent first."""
    rows = db.all_incidents()
    return [_row_to_history_item(row) for row in rows]


@app.get("/incidents/{incident_id}", response_model=IncidentHistoryItem)
def get_incident_detail(incident_id: str) -> IncidentHistoryItem:
    """Read-only single incident lookup by incident_id (the `incidents`
    table primary key — distinct from `thread_id`, the checkpointer key
    used by the approve leg)."""
    row = db.get_incident(incident_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Incident not found.")
    return _row_to_history_item(row)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
