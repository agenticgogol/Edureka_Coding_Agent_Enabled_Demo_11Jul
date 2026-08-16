"""Public entrypoint for this agent module. The FastAPI backend should
import ONLY from this file — never `graph.py`/`state.py`/`tools.py`
directly. See the module README for the full contract.
"""
from __future__ import annotations

import logging
import queue
import threading
import uuid
from typing import Any, Callable, Iterator

from langgraph.types import Command

from . import db
from .budget import TokenBudgetExceededError, incident_budget
from .config import config  # noqa: F401  (import triggers fail-fast key check)
from .graph import build_graph, clear_all_checkpoints, get_checkpointer_cm
from .llm import embed
from .progress import progress_stream

logger = logging.getLogger("incident_backend.interface")

db.init_db()


def _public_view(thread_id: str, values: dict[str, Any], interrupted: bool) -> dict[str, Any]:
    """Translate internal AgentState into the stable public shape the
    backend/frontend consume. Never leaks node names or raw state keys.

    `matched_precedent` was computed by precedent_check and used
    internally (folded into the analysis prompt as a hint the model must
    still independently verify) but never surfaced here — the frontend had
    no way to show the user "found a similar past incident," even when the
    match genuinely fired. Now included on both branches whenever a match
    exists, so the UI can report it."""
    precedent = values.get("matched_precedent")
    precedent_view = (
        {
            "precedent_incident_id": precedent.get("precedent_id"),
            "similarity": precedent.get("similarity"),
            "identified_repo": precedent.get("identified_repo"),
            "identified_file": precedent.get("identified_file"),
            "outcome": precedent.get("outcome"),
        }
        if precedent
        else None
    )

    ticket_id = values.get("ticket_id")
    ticket = db.get_ticket(ticket_id) if ticket_id else None
    ticket_view = None
    if ticket:
        ticket_view = {
            "key": ticket_id,
            "summary": ticket.get("summary"),
            "description": ticket.get("description"),
            "status": ticket.get("status"),
            "url": (
                f"{config.jira_url}/browse/{ticket_id}"
                if config.jira_enabled
                else None
            ),
        }
    patch = values.get("drafted_patch") or {}

    if interrupted:
        return {
            "thread_id": thread_id,
            "status": "pending_approval",
            "incident_id": values.get("incident_id"),
            "identified_repo": values.get("identified_repo"),
            "identified_file": values.get("identified_file"),
            "root_cause": values.get("root_cause"),
            "classification": values.get("classification"),
            "ticket_id": ticket_id,
            "jira_ticket": ticket_view,
            "identified_file": values.get("identified_file"),
            "diff": patch.get("diff"),
            "patch_explanation": patch.get("explanation"),
            "matched_precedent": precedent_view,
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
        "ticket_id": ticket_id,
        "jira_ticket": ticket_view,
        "diff": patch.get("diff"),
        "patch_explanation": patch.get("explanation"),
        "patch_applied": outcome == "closed_pass",
        "test_result": values.get("test_result"),
        "message": values.get("final_message"),
        "matched_precedent": precedent_view,
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
        # incident_budget() is scoped ONLY around the graph invocation, not
        # around _record_incident() below. _record_incident() calls embed()
        # for storage — if that ran while the budget context were still
        # active and already tripped, it would re-raise
        # TokenBudgetExceededError uncaught (this was a real bug: the
        # escalation path crashed instead of degrading cleanly, and the
        # incident never got written to the audit table). Recording an
        # already-finished incident is bookkeeping, not more analysis
        # spend — it must not be constrained by the same cap that stopped
        # the analysis.
        with incident_budget():
            try:
                result = app.invoke(initial_state, config_dict)
            except TokenBudgetExceededError as exc:
                logger.warning("incident %s exceeded token budget: %s", incident_id, exc)
                result = {
                    **initial_state,
                    "outcome": "escalated_ceiling",
                    "final_message": f"Analysis stopped: {exc}",
                }

        interrupted = "__interrupt__" in result
        _record_incident(incident_id, incident_text, result, thread_id)
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
        # See start_incident()'s comment: budget scope stays around ONLY
        # the graph invocation, not the record-keeping call after it.
        with incident_budget():
            try:
                result = app.invoke(Command(resume=resume_payload), config_dict)
            except TokenBudgetExceededError as exc:
                logger.warning("resume for thread_id=%s exceeded token budget: %s", thread_id, exc)
                # Bug fix: the fallback result previously had no
                # incident_id, so _update_incident_record() below was
                # silently skipped — a budget breach during the approve
                # leg never updated the audit row's outcome/test_result,
                # unlike the submit leg (start_incident), which always has
                # incident_id from the initial state it builds itself.
                # Recover it (and any other already-known fields) from the
                # checkpointed state as of just before this failed
                # invocation, so the audit record still gets closed out.
                pre_failure_state = app.get_state(config_dict).values
                result = {
                    **pre_failure_state,
                    "outcome": "escalated_ceiling",
                    "final_message": f"Execution stopped: {exc}",
                }

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


def _record_incident(
    incident_id: str, incident_text: str, result: dict[str, Any], thread_id: str
) -> None:
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
        thread_id=thread_id,
    )


def _update_incident_record(incident_id: str, result: dict[str, Any]) -> None:
    db.update_incident(
        incident_id,
        approval_status=result.get("approval_status"),
        test_result=str(result.get("test_result")),
        outcome=result.get("outcome"),
        drafted_patch_summary=(result.get("drafted_patch") or {}).get("explanation"),
    )


def _stream_call(target_fn: Callable[..., dict[str, Any]], *args: Any, **kwargs: Any) -> Iterator[dict[str, Any]]:
    """Runs a blocking entrypoint (start_incident/resume_incident) in a
    worker thread with a progress sink active, yielding each
    `{"type": "progress", ...}` event as graph.py's nodes emit it, then a
    final `{"type": "result", ...}` event with exactly the same payload
    the non-streaming route would have returned.

    Why a thread + queue rather than making the graph invocation itself
    async/generator-based: LangGraph's `app.invoke()` here is fully
    synchronous, and progress.py's contextvar-based emit_progress() needs
    to be set from the SAME thread that runs the graph (contextvars don't
    propagate across threads) — so the sink is entered inside the worker
    thread's own call stack, not the caller's. This also means
    start_incident/resume_incident's existing logic (budget scoping, audit
    recording, error handling) is reused completely unchanged; only the
    caller's vantage point becomes incremental instead of blocking.

    Any exception raised by target_fn propagates out of this generator
    after the worker thread finishes — same as calling target_fn directly
    would — so a streaming caller sees failures identically to a
    non-streaming one, just after any progress events already emitted."""
    event_queue: "queue.Queue[dict[str, Any] | None]" = queue.Queue()
    result_box: dict[str, Any] = {}
    error_box: list[BaseException] = []

    def worker() -> None:
        with progress_stream(event_queue):
            try:
                result_box["result"] = target_fn(*args, **kwargs)
            except BaseException as exc:  # noqa: BLE001 - re-raised below, not swallowed
                error_box.append(exc)
            finally:
                event_queue.put(None)  # sentinel: worker is done

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

    while True:
        item = event_queue.get()
        if item is None:
            break
        yield item

    thread.join()
    if error_box:
        raise error_box[0]
    yield {"type": "result", **result_box["result"]}


def stream_start_incident(incident_text: str, thread_id: str | None = None) -> Iterator[dict[str, Any]]:
    """Streaming equivalent of start_incident() — same behavior and
    return payload (as the final `type: result` event), plus incremental
    `type: progress` events as the analysis runs."""
    yield from _stream_call(start_incident, incident_text, thread_id=thread_id)


def stream_resume_incident(
    thread_id: str, approved: bool, rejection_note: str | None = None
) -> Iterator[dict[str, Any]]:
    """Streaming equivalent of resume_incident()."""
    yield from _stream_call(
        resume_incident, thread_id, approved=approved, rejection_note=rejection_note
    )


def reset_all_history() -> dict[str, int]:
    """Wipes every trace of prior incidents: the audit table (also the
    precedent-search corpus — resetting clears precedent matching too,
    not just the visible history list), the mocked Jira tickets, and every
    LangGraph checkpoint/write row (so no orphaned thread_id can still be
    resumed/approved after its audit record is gone). Irreversible — no
    soft-delete, no undo. The FastAPI route calling this (backend/main.py)
    is responsible for requiring explicit confirmation; this function
    performs the wipe unconditionally the moment it's called."""
    incidents_deleted = db.delete_all_incidents()
    tickets_deleted = db.delete_all_tickets()
    checkpoints_deleted = clear_all_checkpoints()
    logger.warning(
        "history reset: %d incidents, %d tickets, %d checkpoint threads deleted",
        incidents_deleted, tickets_deleted, checkpoints_deleted,
    )
    return {
        "incidents_deleted": incidents_deleted,
        "tickets_deleted": tickets_deleted,
        "checkpoint_threads_deleted": checkpoints_deleted,
    }
