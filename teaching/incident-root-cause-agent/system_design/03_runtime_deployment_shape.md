# Stage 3: Runtime & Deployment Shape

## Decision walkthrough

1. **Sync (wait in the same request) or async (background, picked up later)?** → **Both, in sequence.** The analysis leg (search repos → find root cause → classify → draft patch/ticket) is short enough to block on synchronously — a normal HTTP request/response the Streamlit UI can wait for. But the human-approval wait that follows is fundamentally asynchronous: a real person reviews the proposed patch on their own schedule, which could be seconds or could be much longer if they're away from the UI. The apply→test→close leg, once approval is given, is again a short synchronous call.

2. **User-request-triggered or event-triggered?** → **User-request-triggered.** Every step is kicked off by a person acting in the Streamlit UI — submitting an incident, or clicking approve/reject on a pending patch. There's no webhook, queue, or cron trigger in this demo (the brief's non-goals explicitly exclude a real external incident-source integration).

3. **Single-item or batch?** → **Single-item.** One incident is processed per invocation; no batch processing of multiple incidents at once.

4. **Must state survive a process restart mid-task?** → **Yes.** The human-approval wait is an indefinite pause by nature (a demo presenter might submit an incident, then pause the walkthrough to explain something, then approve minutes later — or the FastAPI process could restart between those two actions). Combined with the explicit requirement for persisted incident history across restarts, the agent's paused-for-approval state must be checkpointed, not held only in server memory.

5. **Volume / latency / cost ceiling?** → Single-user interactive demo; on the order of single-digit incidents per demo session; no hard latency SLO (a few seconds to ~1 minute per leg is fine); no formal cost ceiling beyond this repo's per-call approval-before-spend rule. Carried forward verbatim to stage 8.

## Chosen runtime shape

**User-request-triggered, durable/checkpointed synchronous legs around an indefinite human-approval pause.**

Concretely, using LangGraph's own interrupt/checkpoint mechanism:
- **Leg 1 (sync):** POST incident → agent runs search/analyze/classify/draft → graph hits the `apply_patch` interrupt → returns "pending approval" immediately. Graph state is checkpointed (not held only in memory) at this pause point.
- **Pause (durable, unbounded duration):** nothing runs; state sits checkpointed until a human acts. Survives a FastAPI restart because the checkpoint is on disk (SQLite), not in-process.
- **Leg 2 (sync):** POST approve/reject → graph resumes from the checkpoint → (if approved) apply_patch → run_tests → close ticket → return final result. (if rejected) → graph ends, ticket stays open with a "patch rejected" note.

This is a combination, not a single label: synchronous request/response for each individual user action, layered on top of durable checkpointing so the gap between those actions can be arbitrarily long without losing state.

## Why

- Q1's "both in sequence" plus Q4 = yes together rule out plain synchronous request/response (an approval wait can't reasonably hold an HTTP connection open) and plain fire-and-forget async (state would be lost on a restart during the wait, and the persisted-history requirement explicitly rules that out).
- Q2/Q3 rule out any event-driven or batch layering — every trigger is a specific person's UI action on one incident.

## Rejected alternative(s)

- **Plain synchronous request/response for the whole flow** — rejected: Q1/Q4. Blocking one HTTP request through an indefinite human-review wait isn't viable, and doesn't survive a restart either.
- **Fire-and-forget async (background job, no restart-survival guarantee)** — rejected: Q4 = yes. The brief requires persisted incident history across restarts, and a demo presenter pausing mid-review is a realistic case where the process could restart before approval — losing the pending patch state would break the HITL story this demo is built to teach.
- **Event-driven** — rejected: Q2. There's no external trigger source in this demo; everything is a direct user action in the Streamlit UI.

## Carried-forward signals for later stages

- Requires persisted/checkpointed state: **yes** — LangGraph checkpointer (SQLite for this demo) persists graph state across the human-approval interrupt and across process restarts; feeds stage 5's memory design directly (this is now a required component, not optional).
- Volume / latency SLO / cost ceiling: single-user interactive demo, single-digit incidents per session, no hard latency SLO (seconds to ~1 minute per leg acceptable), no formal cost ceiling beyond this repo's standing per-call approval rule.

## Status: APPROVED
