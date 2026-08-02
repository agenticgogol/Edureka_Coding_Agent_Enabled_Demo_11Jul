---
name: agent-decision-runtime-deployment-shape
description: Stage 3 of the staged agent-system-design pipeline. Given the usecase, topology, and design pattern already decided, decides the runtime/deployment shape (sync, async, batch, event-driven, durable) before memory is designed. Writes system_design/03_runtime_deployment_shape.md and stops for explicit user approval.
---

# Agent Decision: Runtime & Deployment Shape

Stage 3 of `/agent-system-design`. Decides *how the system executes in
production* — sync request/response, async/long-running, batch, or
event-driven, and whether it needs durable/checkpointed execution. This
has to be decided before memory (stage 5), because whether state must
survive a process restart or a multi-hour wait directly determines what
"task state" memory needs to hold and how it's persisted.

This is a genuinely separate decision from stage 1/2's topology and
pattern choice — a bounded ReAct agent can be sync or durable; a
supervisor-specialists system can be a single HTTP request or a
multi-day event-driven workflow. Don't assume one implies the other.

## When to use

- Called by `/agent-system-design` as stage 3, after stage 2's design
  pattern is approved.
- Requires `system_design/01_agent_topology.md` and
  `system_design/02_design_pattern.md` at `Status: APPROVED`.

## Input

- Usecase + clarifying answers.
- Approved topology and design pattern from stages 1-2.

## Procedure

### 1. Ask the runtime rubric, batched with recommendations

1. **Does the user wait for a response in the same request/connection, or
   can the work happen in the background and be picked up later?**
   *(synchronous / asynchronous — recommend synchronous unless the task
   can genuinely take longer than an interactive UI should block for,
   typically more than a few seconds to low tens of seconds.)*

2. **Is this triggered by a single user request, or by a business event
   (a webhook, a queue message, a cron schedule, a file landing
   somewhere)?** *(user-request-triggered / event-triggered)*

3. **Does a single invocation process one item, or a batch of many items
   with no per-item interactivity?** *(single-item / batch)*

4. **If the work can span minutes to days, or includes a human-review
   wait: does the system need to survive a process restart or deployment
   mid-task without losing progress?** *(no / yes — recommend "yes" for
   anything async with a human-in-the-loop step or multi-hour duration;
   this is what "durable execution" / checkpointing buys you.)*

5. **Expected volume (requests/day, order of magnitude) and any hard
   latency SLO or cost ceiling already set by the business?** *(free
   text — carry forward verbatim to stage 8's cost/latency sub-rubric.)*

### 2. Apply the decision logic

- Q1 = synchronous, Q2 = user-request-triggered, Q3 = single-item →
  **synchronous request/response** (a plain API call or chat turn; no
  special runtime infrastructure needed beyond the app server itself).
- Q1 = asynchronous, Q4 = yes → **durable/checkpointed async workflow**
  (state persisted at each step boundary; survives restarts; required if
  stage 1/2 flagged a human-approval wrapper with a real wait).
- Q1 = asynchronous, Q4 = no → **fire-and-forget async** (background job,
  no restart-survival guarantee needed — cheaper, but state loss on crash
  is acceptable).
- Q2 = event-triggered → **event-driven**, layered on top of whichever of
  the above applies (the trigger mechanism and the execution durability
  are independent choices — name both).
- Q3 = batch → **batch/scheduled**, layered similarly.

State the chosen combination explicitly (e.g. "event-driven, durable
async" is a valid combined answer) — don't force it into a single label
if the real shape is a combination.

### 3. Write `system_design/03_runtime_deployment_shape.md`

```markdown
# Stage 3: Runtime & Deployment Shape

## Decision walkthrough
<Q1-Q5 and answers>

## Chosen runtime shape
<e.g. "event-triggered, durable/checkpointed async workflow">

## Why
<the specific answers that decided each component of the combination>

## Rejected alternative(s)
<e.g. "plain fire-and-forget rejected: Q4 = yes, a multi-hour human
review step means state must survive a restart">

## Carried-forward signals for later stages
- Requires persisted/checkpointed state: <yes/no> (feeds stage 5 memory)
- Volume / latency SLO / cost ceiling: <verbatim from Q5> (feeds stage 8)

## Status: PENDING APPROVAL
```

### 4. Stop and get explicit approval

Same discipline as prior stages.

## Ground rules

- Never assume runtime shape from the design pattern alone — ask
  explicitly, since the same pattern can run sync or durable-async
  depending on the business workflow around it.
- If Q4 = yes but stage 1/2 never flagged a human-approval or
  multi-step-wait need, surface the mismatch and ask rather than silently
  picking durable execution "to be safe" — durable execution has real
  infra cost (checkpoint storage, replay logic) that shouldn't be paid for
  without a reason.
- Always carry the persisted-state signal forward explicitly — stage 5
  must not have to re-derive it from scratch.
