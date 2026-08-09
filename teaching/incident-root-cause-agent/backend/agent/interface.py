"""Public entrypoint for this agent module. The FastAPI backend should
import ONLY from this file — never `graph.py`/`state.py`/`tools.py`
directly. See the module README for the full contract.
"""
from __future__ import annotations

import uuid
from typing import Any

from langgraph.types import Command

from . import db
from .config import config  # noqa: F401  (import triggers fail-fast key check)
from .graph import build_graph, get_checkpointer_cm
from .llm import embed

db.init_db()


def _public_view(thread_id: str, values: dict[str, Any], interrupted: bool) -> dict[str, Any]:
    """Translate internal AgentState into the stable public shape the
    backend/frontend consume. Never leaks node names or raw state keys."""
    if interrupted:
        return {
            "thread_id": thread_id,
            "status": "pending_approval",
            "incident_id": values.get("incident_id"),
            "identified_repo": values.get("identified_repo"),
            "identified_file": values.get("identified_file"),
            "root_cause": values.get("root_cause"),
            "classification": values.get("classification"),
            "ticket_id": values.get("ticket_id"),
            "diff": (values.get("drafted_patch") or {}).get("diff"),
            "patch_explanation": (values.get("drafted_patch") or {}).get("explanation"),
        }

    outcome = values.get("outcome")
    status_map = {
        "infra_resolved": "resolved_infra",
        "closed_pass": "resolved_code_fix",
        "rejected": "rejected",
        "test_failed_after_retry": "failed_after_retry",
        "escalated_ceiling": "escalated",
    }
    return {
        "thread_id": thread_id,
        "status": status_map.get(outcome, "unknown"),
        "incident_id": values.get("incident_id"),
        "identified_repo": values.get("identified_repo"),
        "identified_file": values.get("identified_file"),
        "root_cause": values.get("root_cause"),
        "classification": values.get("classification"),
        "ticket_id": values.get("ticket_id"),
        "test_result": values.get("test_result"),
        "message": values.get("final_message"),
    }


def start_incident(incident_text: str, thread_id: str | None = None) -> dict[str, Any]:
    """Runs the analysis leg for a new incident. Blocks synchronously
    until either a terminal outcome is reached (infra resolution or
    escalation) or the graph pauses at the human-approval interrupt
    (code-issue path). Returns the public view either way — check
    `status`: "pending_approval" means `resume_incident` must be called
    next with the same `thread_id`."""
    thread_id = thread_id or str(uuid.uuid4())
    incident_id = str(uuid.uuid4())
    config_dict = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "incident_id": incident_id,
        "incident_text": incident_text,
        "analysis_tool_calls": 0,
        "execution_tool_calls": 0,
        "escalated": False,
        "draft_retry_used": False,
    }

    with get_checkpointer_cm() as checkpointer:
        app = build_graph(checkpointer)
        result = app.invoke(initial_state, config_dict)

        interrupted = "__interrupt__" in result
        _record_incident(incident_id, incident_text, result)
        return _public_view(thread_id, result, interrupted)


def resume_incident(
    thread_id: str, approved: bool, rejection_note: str | None = None
) -> dict[str, Any]:
    """Resumes a paused incident from its checkpoint (survives a backend
    process restart in between, since the checkpoint is on disk). Approve
    or reject the pending patch. If the post-approval test run fails, the
    graph automatically drafts one revised patch and pauses again at the
    SAME interrupt — call `resume_incident` again for that new round."""
    config_dict = {"configurable": {"thread_id": thread_id}}
    resume_payload = {"approved": approved}
    if rejection_note:
        resume_payload["rejection_note"] = rejection_note

    with get_checkpointer_cm() as checkpointer:
        app = build_graph(checkpointer)
        result = app.invoke(Command(resume=resume_payload), config_dict)

        interrupted = "__interrupt__" in result
        incident_id = result.get("incident_id")
        if incident_id:
            _update_incident_record(incident_id, result)
        return _public_view(thread_id, result, interrupted)


def get_incident_status(thread_id: str) -> dict[str, Any]:
    """Read-only: returns the current state without resuming/advancing
    the graph. Useful for the backend to poll/render UI state."""
    config_dict = {"configurable": {"thread_id": thread_id}}
    with get_checkpointer_cm() as checkpointer:
        app = build_graph(checkpointer)
        state = app.get_state(config_dict)
        interrupted = bool(state.next)
        return _public_view(thread_id, state.values, interrupted)


def _record_incident(incident_id: str, incident_text: str, result: dict[str, Any]) -> None:
    embedding = embed(incident_text)
    db.insert_incident(
        incident_id=incident_id,
        incident_text=incident_text,
        embedding=embedding,
        identified_repo=result.get("identified_repo"),
        identified_file=result.get("identified_file"),
        root_cause=result.get("root_cause"),
        classification=result.get("classification"),
        matched_precedent_id=(result.get("matched_precedent") or {}).get("precedent_id"),
        drafted_patch_summary=(result.get("drafted_patch") or {}).get("explanation"),
        ticket_id=result.get("ticket_id"),
        approval_status=result.get("approval_status"),
        test_result=str(result.get("test_result")),
        outcome=result.get("outcome"),
    )


def _update_incident_record(incident_id: str, result: dict[str, Any]) -> None:
    db.update_incident(
        incident_id,
        approval_status=result.get("approval_status"),
        test_result=str(result.get("test_result")),
        outcome=result.get("outcome"),
        drafted_patch_summary=(result.get("drafted_patch") or {}).get("explanation"),
    )
