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

import json
import os
from typing import Any, Iterator

import requests
import streamlit as st

# ---------------------------------------------------------------------------
# Config — adjust here once the backend's final schema is reconciled.
# ---------------------------------------------------------------------------

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")
INCIDENTS_ENDPOINT = f"{BACKEND_URL}/incidents"

# Backend now requires X-API-Key on every route except /health (see
# backend/auth.py) — must match one of the comma-separated
# INCIDENT_AGENT_API_KEYS the backend was started with.
API_KEY = os.environ.get("INCIDENT_AGENT_API_KEY", "")
_AUTH_HEADERS = {"X-API-Key": API_KEY}


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

if not API_KEY:
    st.error(
        "INCIDENT_AGENT_API_KEY is not set for this Streamlit process — "
        "every backend call will get a 401. Set it to one of the backend's "
        "configured INCIDENT_AGENT_API_KEYS values before using this UI, "
        "then restart Streamlit."
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
if "reset_form_version" not in st.session_state:
    st.session_state.reset_form_version = 0
if "github_scan" not in st.session_state:
    st.session_state.github_scan = None
if "github_ticket" not in st.session_state:
    st.session_state.github_ticket = {}


# ---------------------------------------------------------------------------
# Backend calls
# ---------------------------------------------------------------------------

def submit_incident(text: str) -> dict[str, Any] | None:
    # Backend's SubmitIncidentRequest expects "incident_text", not "text".
    try:
        resp = requests.post(
            INCIDENTS_ENDPOINT,
            json={"incident_text": text},
            headers=_AUTH_HEADERS,
            timeout=REQUEST_TIMEOUT_S,
        )
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
            headers=_AUTH_HEADERS,
            timeout=REQUEST_TIMEOUT_S,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as exc:
        st.error(f"Could not reach the backend at `{approve_endpoint(thread_id)}`: {exc}")
        return None


def _iter_sse_events(resp: requests.Response) -> Iterator[dict[str, Any]]:
    """Parses `data: {json}` SSE lines from a streaming response into
    dicts. Each event this backend sends is single-line JSON (no
    multi-line `data:` continuation, no `event:`/`id:` fields) — see
    backend/main.py's `_sse_event()` — so this only needs to handle that
    one shape, not the full SSE spec."""
    for line in resp.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data: "):
            continue
        yield json.loads(line[len("data: ") :])


def stream_submit_incident(text: str) -> Iterator[dict[str, Any]]:
    resp = requests.post(
        f"{BACKEND_URL}/incidents/stream",
        json={"incident_text": text},
        headers=_AUTH_HEADERS,
        stream=True,
        timeout=REQUEST_TIMEOUT_S,
    )
    resp.raise_for_status()
    yield from _iter_sse_events(resp)


def stream_submit_decision(
    thread_id: str, approved: bool, rejection_note: str | None = None
) -> Iterator[dict[str, Any]]:
    resp = requests.post(
        f"{approve_endpoint(thread_id)}/stream",
        json={"approved": approved, "rejection_note": rejection_note},
        headers=_AUTH_HEADERS,
        stream=True,
        timeout=REQUEST_TIMEOUT_S,
    )
    resp.raise_for_status()
    yield from _iter_sse_events(resp)


def run_streamed(events: Iterator[dict[str, Any]], status_label: str) -> dict[str, Any] | None:
    """Drives an SSE event generator inside a live st.status() box —
    each `type: progress` event appends a line, `type: result` becomes
    the return value, `type: error` surfaces as st.error() and returns
    None (mirroring the blocking helpers' None-on-failure contract)."""
    try:
        with st.status(status_label, expanded=True) as status_box:
            for event in events:
                if event["type"] == "progress":
                    status_box.write(event["message"])
                elif event["type"] == "error":
                    status_box.update(label="Failed", state="error")
                    st.error(event.get("message", "The agent run failed."))
                    return None
                elif event["type"] == "result":
                    status_box.update(label=f"{status_label} — done", state="complete")
                    return event
    except requests.exceptions.RequestException as exc:
        st.error(f"Could not reach the backend: {exc}")
        return None
    return None


def fetch_history() -> list[dict[str, Any]] | None:
    try:
        resp = requests.get(INCIDENTS_ENDPOINT, headers=_AUTH_HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        # tolerate either a bare list or a {"incidents": [...]} wrapper
        if isinstance(data, dict):
            data = data.get("incidents", [])
        return data
    except requests.exceptions.RequestException as exc:
        st.error(f"Could not reach the backend at `{INCIDENTS_ENDPOINT}`: {exc}")
        return None


def reset_history() -> dict[str, Any] | None:
    # Backend requires ?confirm=true explicitly (see backend/main.py) — a
    # bare DELETE is rejected with 400 rather than silently doing nothing,
    # so the UI-level confirmation step below is a genuine second gate, not
    # just cosmetic.
    try:
        resp = requests.delete(
            INCIDENTS_ENDPOINT,
            params={"confirm": "true"},
            headers=_AUTH_HEADERS,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as exc:
        st.error(f"Could not reach the backend at `{INCIDENTS_ENDPOINT}`: {exc}")
        return None


def scan_github_repository(repository: str, request: str) -> dict[str, Any] | None:
    try:
        resp = requests.post(
            f"{BACKEND_URL}/github/scan",
            json={"repository": repository, "request": request},
            headers=_AUTH_HEADERS,
            timeout=REQUEST_TIMEOUT_S,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as exc:
        st.error(f"GitHub scan failed: {exc}")
        return None


def create_github_ticket(repository: str, finding: dict[str, Any]) -> dict[str, Any] | None:
    try:
        resp = requests.post(
            f"{BACKEND_URL}/github/tickets",
            json={"repository": repository, "finding": finding},
            headers=_AUTH_HEADERS,
            timeout=REQUEST_TIMEOUT_S,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as exc:
        st.error(f"Jira ticket creation failed: {exc}")
        return None


def close_github_ticket(ticket_id: str) -> dict[str, Any] | None:
    try:
        resp = requests.post(
            f"{BACKEND_URL}/github/tickets/{ticket_id}/close",
            json={"confirmed": True},
            headers=_AUTH_HEADERS,
            timeout=REQUEST_TIMEOUT_S,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as exc:
        st.error(f"Jira ticket close failed: {exc}")
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


def render_precedent_callout(result: dict[str, Any]) -> None:
    """Surfaces precedent_check's match, if any, before the rest of the
    result — the agent always independently re-verifies the root cause
    even when a precedent is found, so this is framed as a hint the agent
    used, not as the finding itself."""
    precedent = _get(result, "matched_precedent")
    if not precedent:
        return
    similarity = precedent.get("similarity")
    similarity_str = f"{similarity:.0%} similar" if isinstance(similarity, (int, float)) else "similar"
    prior_repo = precedent.get("identified_repo")
    prior_outcome = precedent.get("outcome")
    detail = f" (`{prior_repo}`, outcome: `{prior_outcome}`)" if prior_repo else ""
    st.info(
        f"🔎 Found a similar past incident ({similarity_str}){detail} — used as a starting "
        "hint, but the agent independently re-verified the root cause by reading the code "
        "itself rather than reusing the prior finding verbatim."
    )


def render_incident_result(result: dict[str, Any]) -> None:
    classification = _get(result, "classification", default="").lower()
    status = _get(result, "status", default="").lower()

    render_precedent_callout(result)

    if classification in ("code_issue", "code-issue", "code"):
        st.subheader("Root cause (code issue)")
        st.write(_get(result, "root_cause", "rootCause", default="(no root cause text returned)"))

        repo = _get(result, "repo", "identified_repo")
        if repo:
            st.caption(f"Repository: `{repo}`")

        st.subheader("Proposed code change")
        file_path = _get(result, "identified_file", default="")
        if file_path:
            st.write(f"**File to change:** `{repo}/{file_path}`")
        patch = _get(result, "patch", "drafted_patch", "diff", default="")
        if patch:
            st.code(patch, language="diff")
        else:
            st.error("The backend did not return a patch diff for this code issue.")

        patch_explanation = _get(result, "patch_explanation")
        if patch_explanation:
            st.caption(patch_explanation)

        st.subheader("Jira ticket")
        ticket = _get(result, "jira_ticket", "ticket", default={})
        ticket_id = _get(result, "ticket_id")
        if ticket:
            key = _get(ticket, "key", "ticket_id", default=ticket_id)
            url = _get(ticket, "url")
            if url:
                st.markdown(f"**Issue:** [{key}]({url})")
            else:
                st.write(f"**Issue:** `{key}`")
            st.write(f"**Summary:** {_get(ticket, 'summary', default='—')}")
            st.write(f"**Status:** {_get(ticket, 'status', default='—')}")
            description = _get(ticket, "description", default="")
            if description:
                with st.expander("Jira description (includes the patch)", expanded=True):
                    st.code(description, language="text")
        elif ticket_id:
            st.write(f"**Ticket:** `{ticket_id}`")
        else:
            st.write("(no ticket returned)")

        if status == "pending_approval" or "pending" in status:
            st.divider()
            st.write("**Awaiting your decision** — nothing has been applied yet.")
            col1, col2 = st.columns(2)
            thread_id = _get(result, "thread_id", "incident_id", "id")
            streaming_enabled = st.session_state.get("streaming_enabled", False)
            with col1:
                if st.button("Approve", type="primary", use_container_width=True):
                    if streaming_enabled:
                        final = run_streamed(
                            stream_submit_decision(thread_id, approved=True),
                            "Applying patch and re-running tests...",
                        )
                    else:
                        with st.spinner("Applying patch and re-running tests..."):
                            final = submit_decision(thread_id, approved=True)
                    if final is not None:
                        _handle_approval_response(final)
            with col2:
                if st.button("Reject", use_container_width=True):
                    if streaming_enabled:
                        final = run_streamed(
                            stream_submit_decision(thread_id, approved=False),
                            "Recording rejection...",
                        )
                    else:
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

    # Keep the complete change evidence visible after the approval leg too;
    # the terminal backend response now carries the same diff and Jira view
    # as the pending-approval response.
    if _get(result, "diff", "patch", "drafted_patch") or _get(result, "jira_ticket", "ticket"):
        st.subheader("Code change and Jira evidence")
        repo = _get(result, "identified_repo", "repo", default="")
        file_path = _get(result, "identified_file", default="")
        if repo or file_path:
            st.write(f"**File:** `{repo}/{file_path}`")
        diff = _get(result, "diff", "patch", "drafted_patch", default="")
        if diff:
            st.code(diff, language="diff")
        ticket = _get(result, "jira_ticket", "ticket", default={})
        ticket_id = _get(result, "ticket_id")
        if ticket:
            key = _get(ticket, "key", "ticket_id", default=ticket_id)
            url = _get(ticket, "url")
            if url:
                st.markdown(f"**Jira issue:** [{key}]({url})")
            else:
                st.write(f"**Jira issue:** `{key}`")
            st.write(f"**Jira status:** {_get(ticket, 'status', default='—')}")
            description = _get(ticket, "description", default="")
            if description:
                with st.expander("Jira description", expanded=True):
                    st.code(description, language="text")
        elif ticket_id:
            st.write(f"**Jira issue:** `{ticket_id}`")

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
# GitHub repository workflow
# ---------------------------------------------------------------------------

def render_github_workflow() -> None:
    st.subheader("GitHub repository bug scan")
    st.caption(
        "The scan is read-only. The agent will not create branches, commits, pull requests, "
        "or push changes. You will apply and push any accepted patch manually."
    )
    repository = st.text_input(
        "GitHub repository",
        placeholder="owner/repository or https://github.com/owner/repository",
        key="github_repository",
    )
    request = st.text_area(
        "Scan request",
        value="Find probable bugs and incident causes across this repository.",
        key="github_scan_request",
        height=90,
    )
    consent = st.checkbox(
        "I authorize the agent to read this repository's source files through GitHub MCP.",
        key="github_read_consent",
    )
    if st.button("Scan repository for probable bugs", type="primary", disabled=not consent):
        if not repository.strip():
            st.warning("Enter a GitHub repository first.")
        else:
            st.session_state.github_ticket = {}
            with st.spinner("Reading repository files through GitHub MCP and analyzing them..."):
                st.session_state.github_scan = scan_github_repository(repository.strip(), request.strip())

    scan = st.session_state.github_scan
    if not scan:
        return
    st.divider()
    st.write(f"**Repository:** `{scan.get('repository', repository)}`")
    files_read = scan.get("files_read", [])
    st.write(f"**Files read:** {len(files_read)}")
    with st.expander("Files read by GitHub MCP", expanded=True):
        if files_read:
            for path in files_read:
                st.code(path, language="text")
        else:
            st.warning("The MCP scan returned no source files.")
    findings = scan.get("findings", [])
    if not findings:
        st.success("No credible probable bugs were found in the files scanned.")
        return
    st.warning(f"Found {len(findings)} probable issue(s). Review the evidence before creating Jira.")
    for index, finding in enumerate(findings):
        title = finding.get("title", f"Probable issue {index + 1}")
        with st.expander(f"{finding.get('severity', 'unknown').upper()}: {title}", expanded=index == 0):
            st.write(f"**File:** `{finding.get('file', 'unknown')}`")
            if finding.get("line"):
                st.write(f"**Line:** `{finding['line']}`")
            if finding.get("confidence") is not None:
                st.write(f"**Confidence:** {float(finding['confidence']):.0%}")
            st.write(f"**Evidence:** {finding.get('evidence', '—')}")
            st.write(f"**Trigger scenario:** {finding.get('trigger_scenario', '—')}")
            st.write(f"**Root cause:** {finding.get('root_cause', '—')}")
            st.write(f"**Impact:** {finding.get('impact', '—')}")
            st.write("**Proposed patch (apply manually):**")
            st.code(finding.get("unified_diff", "(no patch proposed)"), language="diff")
            st.write("The agent will not push this patch or create a branch/PR.")

    tickets = st.session_state.github_ticket
    if not isinstance(tickets, dict):
        tickets = {}
        st.session_state.github_ticket = tickets
    for index, finding in enumerate(findings):
        ticket_response = tickets.get(str(index))
        if not ticket_response:
            create_consent = st.checkbox(
                "Create a Jira ticket for this probable issue.",
                key=f"github_create_ticket_consent_{index}",
            )
            if st.button("Create Jira ticket", key=f"create_github_ticket_{index}", disabled=not create_consent):
                with st.spinner("Creating Jira ticket..."):
                    created = create_github_ticket(scan.get("repository", repository), finding)
                if created:
                    tickets[str(index)] = created
                    st.rerun()
            continue

        if ticket_response.get("ticket"):
            ticket = ticket_response["ticket"]
            key = ticket.get("key", ticket.get("ticket_id"))
            url = ticket.get("url")
            st.success(f"Jira ticket created for issue {index + 1}. Apply the patch manually, then confirm below.")
            if url:
                st.markdown(f"**Jira issue:** [{key}]({url})")
            else:
                st.write(f"**Jira issue:** `{key}`")
            st.write(f"**Jira status:** {ticket.get('status', 'open')}")
            with st.expander("Jira description", expanded=True):
                st.code(ticket.get("description", ""), language="text")
            pushed = st.checkbox(
                "I manually applied the patch and pushed/merged it in GitHub.",
                key=f"github_patch_confirmed_{index}",
            )
            if st.button("Confirm patch and close Jira ticket", key=f"close_github_ticket_{index}", disabled=not pushed):
                with st.spinner("Closing Jira ticket..."):
                    closed = close_github_ticket(key)
                if closed:
                    tickets[str(index)] = closed
                    st.success("Human confirmation recorded. Jira ticket closed.")


# ---------------------------------------------------------------------------
# Main: select code source
# ---------------------------------------------------------------------------

source = st.radio("Code source", ["Local repository", "GitHub repository"], horizontal=True)
if source == "GitHub repository":
    render_github_workflow()
else:
    incident_text = st.text_area(
        "Describe the incident",
        placeholder='e.g. "checkout API returns 500 on large carts"',
        height=120,
    )

    streaming_enabled = st.checkbox(
        "Stream response (show step-by-step progress instead of waiting silently)",
        key="streaming_enabled",
        help=(
            "Shows live progress — precedent check, repo search, classification, "
            "patch drafting — as the agent works, instead of one blocking wait. "
            "Same result either way; this only changes how it's delivered."
        ),
    )

    if st.button("Submit incident", type="primary"):
        if not incident_text.strip():
            st.warning("Please describe the incident before submitting.")
        elif streaming_enabled:
            result = run_streamed(
                stream_submit_incident(incident_text.strip()), "Analyzing incident..."
            )
            if result is not None:
                st.session_state.current_incident = result
                st.session_state.final_result = None
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

    st.divider()
    with st.expander("⚠️ Reset history"):
        st.caption(
            "Permanently deletes every incident, mocked Jira ticket, and "
            "in-progress approval — including this session's precedent-match "
            "corpus. Cannot be undone."
        )
        confirm_key = f"confirm_reset_history_{st.session_state.reset_form_version}"
        confirm_reset = st.checkbox("I understand this cannot be undone", key=confirm_key)
        if st.button(
            "Reset history",
            type="primary",
            disabled=not confirm_reset,
            help="Check the box above to enable this button.",
        ):
            with st.spinner("Wiping incident history..."):
                result = reset_history()
            if result is not None:
                st.success(
                    f"Deleted {result['incidents_deleted']} incident(s), "
                    f"{result['tickets_deleted']} ticket(s), "
                    f"{result['checkpoint_threads_deleted']} in-progress approval(s)."
                )
                st.session_state.history = []
                st.session_state.current_incident = None
                st.session_state.final_result = None
                # Do not mutate a widget-owned key after the checkbox has been
                # instantiated; changing the form version creates a fresh
                # unchecked checkbox on the next rerun.
                st.session_state.reset_form_version += 1
                st.rerun()
