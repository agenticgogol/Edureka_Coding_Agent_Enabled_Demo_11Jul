# Incident Root-Cause Agent — FastAPI backend

Wraps `backend/agent/interface.py` (already built, LangGraph bounded-ReAct
agent) in an HTTP API for the Streamlit frontend. This file only imports
`backend.agent.interface` and `backend.agent.db` — never the LangGraph
internals directly.

## Run

From `teaching/incident-root-cause-agent/`:

```bash
pip install -r backend/requirements.txt
export OPENAI_API_KEY=...   # required — no mock mode
uvicorn backend.main:app --reload
```

Docs at `http://127.0.0.1:8000/docs` once running.

## Endpoints

### `POST /incidents`

Submit leg. Blocks synchronously through the analysis leg (precedent
check -> repo/root-cause search -> classification -> draft, or infra
resolution, or step-ceiling escalation).

Request:
```json
{ "incident_text": "checkout API returns 500 on large carts" }
```

Response (`200`, shape varies by `status`):
```json
{
  "thread_id": "uuid",
  "status": "pending_approval | resolved_infra | escalated",
  "incident_id": "uuid",
  "identified_repo": "checkout-service",
  "identified_file": "cart.py",
  "root_cause": "...",
  "classification": "code_issue | infra_issue",
  "ticket_id": "JIRA-...",
  "diff": "... (only when status == pending_approval)",
  "patch_explanation": "... (only when status == pending_approval)",
  "test_result": null,
  "message": "... (informational text for resolved_infra / escalated)"
}
```

Save `thread_id` from the response — it's required for the approve leg.
Errors: `500` on unexpected agent failure (message only, no stack trace).

### `POST /incidents/{thread_id}/approve`

Approve/reject leg. Only valid when the incident identified by
`thread_id` is currently `pending_approval`. Resumes the graph from its
checkpoint; if approved, blocks through apply_patch -> run_tests ->
close_jira_ticket (including the one post-approval draft_patch retry,
which re-enters `pending_approval` — call this endpoint again in that case).

Request:
```json
{ "approved": true, "rejection_note": null }
```

Response (`200`), same flat shape as above, with `status` now one of:
`resolved_code_fix | rejected | failed_after_retry | pending_approval` (retry case).

Errors:
- `404` — no incident found for `thread_id`.
- `409` — incident is not currently `pending_approval` (already terminal,
  or was never in a pending state).
- `500` — unexpected agent failure.

### `GET /incidents`

Read-only audit history from the shared SQLite `incidents` table, most
recent first. Array of incident records (see `IncidentHistoryItem` in
`main.py`) — includes `id`, `created_at`, `incident_text`,
`identified_repo`, `identified_file`, `root_cause`, `classification`,
`matched_precedent_id`, `drafted_patch_summary`, `ticket_id`,
`approval_status`, `test_result`, `outcome`.

Note: `id` here is the incident's `incidents`-table primary key
(`incident_id`), **not** the LangGraph `thread_id` used by the approve
leg — the two are different identifiers returned separately by
`start_incident`.

### `GET /incidents/{incident_id}`

Read-only single incident lookup by the audit-table `incident_id`.
`404` if not found.

### `GET /health`

Liveness check, `{"status": "ok"}`.

## Not verified with real API calls

This backend's routes were verified structurally (schema validation,
routing, 404/409 error paths) with `backend.agent.interface` mocked at the
import boundary — no real OpenAI calls were made during this build, per
this repo's no-agent-spends-real-API-money-without-approval rule. A real
end-to-end run (`uvicorn` + live `POST /incidents` + `POST .../approve`)
still needs to happen under `run-and-verify` with explicit cost approval.
