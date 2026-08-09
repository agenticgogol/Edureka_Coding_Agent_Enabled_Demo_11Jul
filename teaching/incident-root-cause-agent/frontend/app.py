"""Streamlit frontend for the incident root-cause triage agent.

Flow: a dev/SRE types a free-form incident description, the FastAPI backend
(../backend) runs a bounded ReAct LangGraph agent (precedent check -> repo
search -> root-cause analysis -> classification) and returns one of three
outcomes:

  - code issue: root cause, a drafted patch, a mocked Jira ticket, and an
    Approve/Reject control (patch not yet applied — human-in-the-loop
    interrupt).
  - infra issue: an informational message recommending the user check with
    the system admin. No approval step.
  - honest incompleteness: a "could not confidently determine root cause
    within the step budget" message with whatever partial findings exist.

Approving or rejecting resumes the checkpointed graph on the backend via a
second endpoint and shows the final outcome (patch applied + tests +
ticket closed, or a rejection confirmation).

No API keys are collected or used here — this UI never calls OpenAI (or any
LLM provider) directly. All LLM calls happen backend-side.

--------------------------------------------------------------------------
API contract this UI expects (see design.md / architecture_design.md).
Endpoint paths and field names are the integrator's reconciliation point
if the backend-builder's final schema differs — everything network-related
is kept in this one config section plus the small `_call_*` wrappers below
so it's a quick fix, not a rewrite.

POST {BACKEND_URL}/incidents
  request:  {"text": "<free-form incident description>"}
  response (code issue):
    {
      "incident_id": "<str>",
      "classification": "code_issue",
      "repo": "<str>",
      "root_cause": "<str>",
      "patch": "<unified diff str>",
      "jira_ticket": {"key": "<str>", "summary": "<str>", "description": "<str>", "status": "<str>"},
      "status": "pending_approval"
    }
  response (infra issue):
    {
      "incident_id": "<str>",
      "classification": "infra_issue",
      "message": "<str>",
      "status": "resolved"
    }
  response (honest incompleteness):
    {
      "incident_id": "<str>",
      "classification": "unknown",
      "message": "<str>",
      "partial_findings": "<str or list[str], optional>",
      "status": "incomplete"
    }

POST {BACKEND_URL}/incidents/{incident_id}/approve
  request:  {"decision": "approved"} or {"decision": "rejected"}
  response (approved, tests pass):
    {
      "incident_id": "<str>",
      "status": "closed",
      "patch_applied": true,
      "test_result": "<str, e.g. 'passed'>",
      "ticket_status": "closed"
    }
  response (approved, tests fail after retry):
    {
      "incident_id": "<str>",
      "status": "pending_approval" | "failed",
      "patch_applied": false,
      "test_result": "<str, e.g. 'failed'>",
      "message": "<str>"
    }
  response (rejected):
    {
      "incident_id": "<str>",
      "status": "rejected",
      "message": "<str>"
    }

GET {BACKEND_URL}/incidents
  response: [
    {
      "incident_id": "<str>",
      "text": "<str>",
      "repo": "<str, optional>",
      "classification": "<str>",
      "status": "<str>",
      "created_at": "<ISO timestamp str>"
    },
    ...
  ]
--------------------------------------------------------------------------
"""
from __future__ import annotations

import os
from typing import Any

import requests
import streamlit as st

# ---------------------------------------------------------------------------
# Config — adjust here once the backend's final schema is reconciled.
# ---------------------------------------------------------------------------

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")
INCIDENTS_ENDPOINT = f"{BACKEND_URL}/incidents"


def approve_endpoint(thread_id: str) -> str:
    # Backend route is keyed by thread_id (LangGraph checkpoint id).
    return f"{BACKEND_URL}/incidents/{thread_id}/approve"


REQUEST_TIMEOUT_S = 120  # analysis leg can involve several tool calls

st.set_page_config(page_title="Incident Root-Cause Triage Agent", page_icon="🛠️", layout="wide")
st.title("🛠️ Incident Root-Cause Triage Agent")
st.caption(
    "Describe an incident in plain English. The agent searches the synthetic "
    "repos, finds the root cause, and either drafts a patch for your approval "
    "or tells you it's an infra issue — or, if it can't tell, says so honestly."
)

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

if "current_incident" not in st.session_state:
    st.session_state.current_incident = None  # last POST /incidents response (dict)
if "final_result" not in st.session_state:
    st.session_state.final_result = None  # last POST /incidents/{id}/approve response (dict)
if "history" not in st.session_state:
    st.session_state.history = None  # cached GET /incidents response (list[dict])


# ---------------------------------------------------------------------------
# Backend calls
# ---------------------------------------------------------------------------

def submit_incident(text: str) -> dict[str, Any] | None:
    # Backend's SubmitIncidentRequest expects "incident_text", not "text".
    try:
        resp = requests.post(INCIDENTS_ENDPOINT, json={"incident_text": text}, timeout=REQUEST_TIMEOUT_S)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as exc:
        st.error(f"Could not reach the backend at `{INCIDENTS_ENDPOINT}`: {exc}")
        return None


def submit_decision(thread_id: str, approved: bool, rejection_note: str | None = None) -> dict[str, Any] | None:
    # Backend's approve route is keyed by thread_id (the LangGraph checkpoint
    # id), not incident_id, and expects {"approved": bool, "rejection_note": ...}.
    try:
        resp = requests.post(
            approve_endpoint(thread_id),
            json={"approved": approved, "rejection_note": rejection_note},
            timeout=REQUEST_TIMEOUT_S,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as exc:
        st.error(f"Could not reach the backend at `{approve_endpoint(thread_id)}`: {exc}")
        return None


def fetch_history() -> list[dict[str, Any]] | None:
    try:
        resp = requests.get(INCIDENTS_ENDPOINT, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        # tolerate either a bare list or a {"incidents": [...]} wrapper
        if isinstance(data, dict):
            data = data.get("incidents", [])
        return data
    except requests.exceptions.RequestException as exc:
        st.error(f"Could not reach the backend at `{INCIDENTS_ENDPOINT}`: {exc}")
        return None


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------

def _get(d: dict, *keys: str, default=None):
    """Returns the first present, non-None key from `keys` — a small
    tolerance layer for field-name drift against the backend's final
    schema (e.g. 'root_cause' vs 'rootCause')."""
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default


def _handle_approval_response(final: dict[str, Any]) -> None:
    """Route an approve/reject response. Per backend/agent/README.md, a
    post-approval test failure triggers exactly one draft_patch retry that
    re-enters the SAME pending_approval interrupt with a revised patch —
    in that case show the approve/reject UI again (not the final screen)."""
    status = _get(final, "status", default="").lower()
    if status == "pending_approval" or "pending" in status:
        st.session_state.current_incident = final
        st.session_state.final_result = None
    else:
        st.session_state.final_result = final
    st.rerun()


def render_incident_result(result: dict[str, Any]) -> None:
    classification = _get(result, "classification", default="").lower()
    status = _get(result, "status", default="").lower()

    if classification in ("code_issue", "code-issue", "code"):
        st.subheader("Root cause (code issue)")
        st.write(_get(result, "root_cause", "rootCause", default="(no root cause text returned)"))

        repo = _get(result, "repo", "identified_repo")
        if repo:
            st.caption(f"Repository: `{repo}`")

        st.subheader("Drafted patch")
        patch = _get(result, "patch", "drafted_patch", "diff", default="")
        st.code(patch or "(no patch returned)", language="diff")

        patch_explanation = _get(result, "patch_explanation")
        if patch_explanation:
            st.caption(patch_explanation)

        st.subheader("Mocked Jira ticket")
        # Backend returns only a "ticket_id" string, not a full ticket object.
        ticket = _get(result, "jira_ticket", "ticket", default={})
        ticket_id = _get(result, "ticket_id")
        if ticket:
            st.json(ticket)
        elif ticket_id:
            st.write(f"**Ticket:** `{ticket_id}`")
        else:
            st.write("(no ticket returned)")

        if status == "pending_approval" or "pending" in status:
            st.divider()
            st.write("**Awaiting your decision** — nothing has been applied yet.")
            col1, col2 = st.columns(2)
            thread_id = _get(result, "thread_id", "incident_id", "id")
            with col1:
                if st.button("Approve", type="primary", use_container_width=True):
                    with st.spinner("Applying patch and re-running tests..."):
                        final = submit_decision(thread_id, approved=True)
                    if final is not None:
                        _handle_approval_response(final)
            with col2:
                if st.button("Reject", use_container_width=True):
                    with st.spinner("Recording rejection..."):
                        final = submit_decision(thread_id, approved=False)
                    if final is not None:
                        _handle_approval_response(final)
        else:
            st.info(f"Status: {status or '(unknown)'}")

    elif classification in ("infra_issue", "infra-issue", "infra"):
        st.subheader("Infra / setup issue")
        st.info(
            _get(
                result,
                "message",
                default="This looks like an infra/setup issue. Please check with the system admin.",
            )
        )

    else:
        st.subheader("Could not confidently determine root cause")
        st.warning(
            _get(
                result,
                "message",
                default="The agent could not confidently determine a root cause within its step budget.",
            )
        )
        partial = _get(result, "partial_findings")
        if partial:
            st.write("**Partial findings:**")
            if isinstance(partial, list):
                for item in partial:
                    st.write(f"- {item}")
            else:
                st.write(partial)


def render_final_result(result: dict[str, Any]) -> None:
    # Backend's terminal statuses are "resolved_code_fix", "rejected",
    # "failed_after_retry" (see backend/main.py's _TERMINAL_STATUSES);
    # there is no separate patch_applied/ticket_status field — infer from
    # status + ticket_id instead.
    status = _get(result, "status", default="").lower()

    if status in ("closed", "resolved", "resolved_code_fix") or _get(result, "patch_applied") is True:
        st.success("Patch applied and ticket closed.")
        test_result = _get(result, "test_result", "testResult")
        if test_result:
            st.write(f"**Test result:** {test_result}")
        ticket_status = _get(result, "ticket_status", "ticketStatus")
        ticket_id = _get(result, "ticket_id")
        if ticket_status:
            st.write(f"**Ticket status:** {ticket_status}")
        elif ticket_id:
            st.write(f"**Ticket:** `{ticket_id}` closed")
    elif status == "rejected":
        st.warning("Change rejected. Ticket left open; no patch applied.")
        message = _get(result, "message")
        if message:
            st.write(message)
    elif status in ("failed", "failed_after_retry") or (
        _get(result, "patch_applied") is False and _get(result, "test_result")
    ):
        st.error("Post-approval test run failed (after one retry).")
        test_result = _get(result, "test_result", "testResult")
        if test_result:
            st.write(f"**Test result:** {test_result}")
        message = _get(result, "message")
        if message:
            st.write(message)
    else:
        st.write("**Result:**")
        st.json(result)


# ---------------------------------------------------------------------------
# Main: submit incident
# ---------------------------------------------------------------------------

incident_text = st.text_area(
    "Describe the incident",
    placeholder='e.g. "checkout API returns 500 on large carts"',
    height=120,
)

if st.button("Submit incident", type="primary"):
    if not incident_text.strip():
        st.warning("Please describe the incident before submitting.")
    else:
        with st.spinner("Agent is searching repos and analyzing the incident..."):
            result = submit_incident(incident_text.strip())
        if result is not None:
            st.session_state.current_incident = result
            st.session_state.final_result = None

if st.session_state.final_result is not None:
    st.divider()
    render_final_result(st.session_state.final_result)
    if st.button("Submit another incident"):
        st.session_state.current_incident = None
        st.session_state.final_result = None
        st.rerun()
elif st.session_state.current_incident is not None:
    st.divider()
    render_incident_result(st.session_state.current_incident)

# ---------------------------------------------------------------------------
# Sidebar: incident history
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("Incident history")
    if st.button("Refresh history"):
        st.session_state.history = fetch_history()

    if st.session_state.history is None:
        st.session_state.history = fetch_history()

    history = st.session_state.history or []
    if not history:
        st.caption("No past incidents yet.")
    else:
        for item in history:
            text = _get(item, "text", "incident_text", default="")
            truncated = (text[:80] + "...") if len(text) > 80 else text
            repo = _get(item, "repo", "identified_repo", default="—")
            classification = _get(item, "classification", default="—")
            status = _get(item, "status", "outcome", "approval_status", default="—")
            created_at = _get(item, "created_at", "timestamp", default="—")

            with st.expander(truncated or "(no text)"):
                st.write(f"**Repo:** {repo}")
                st.write(f"**Classification:** {classification}")
                st.write(f"**Status:** {status}")
                st.write(f"**When:** {created_at}")
