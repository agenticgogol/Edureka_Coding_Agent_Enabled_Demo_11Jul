---
name: agent-decision-tools-and-authorization
description: Stage 4 of the staged agent-system-design pipeline. Given the usecase, topology, design pattern, and runtime shape already decided, inventories every tool the agent(s) need, sources every external one (free first, then paid with approval, then a concrete alternative approach, then an explicit capability-loss confirmation if nothing else works) via agent-decision-external-tool-sourcing, and decides read/write boundary, authorization, idempotency, and audit requirements per tool. Writes system_design/04_tools_and_authorization.md and stops for explicit user approval.
---

# Agent Decision: Tools & Authorization Boundary

Stage 4 of `/agent-system-design`. Decides *what the agent can actually
do* — the full tool inventory and, for every tool, whether it reads or
writes, who/what authorizes it, and what idempotency/audit guarantees it
needs. This has to be decided before memory (stage 5), because a tool
that mutates state or requires human approval directly shapes what "task
state" and "audit history" memory need to hold — you can't design memory
around tools you haven't enumerated yet.

## When to use

- Called by `/agent-system-design` as stage 4, after stage 3's runtime
  shape is approved.
- Requires stages 1-3 at `Status: APPROVED`.

## Input

- Usecase + clarifying answers.
- Approved topology, design pattern, and runtime shape from stages 1-3.
- The high-impact/irreversible flag carried from stage 1.

## Procedure

### 1. Enumerate every tool the usecase actually needs

Ask directly, in plain language, not multiple choice: "Walk me through
every distinct action this system needs to take — every lookup, every
write, every external API call, every side effect." Don't let the user
under-specify with "it queries the database" — press for the actual
distinct operations (e.g. "look up account," "check balance," "issue
refund" are three separate tools with three different risk profiles, not
one "database access" tool).

### 2. Classify each tool as custom or external, and source external ones first

For every tool from step 1, decide: **custom** (in-house logic, no
third-party dependency) or **external** (calls a third-party API/SaaS —
web search, geocoding, SMS/email delivery, data enrichment, payment
processing, etc.).

For every **external** tool, invoke `agent-decision-external-tool-sourcing`
now, before running the auth rubric below — it researches free options,
gets a real yes/no on paid cost if no free option covers the need, and if
declined, searches for concrete alternative approaches (e.g. a public
site the agent can browse instead of a paid data API) before asking the
user to accept any remaining capability loss. Carry its returned sourcing
record forward into this stage's output file (step 5). If that skill's
outcome is "declined — omitted," this tool is dropped from the inventory
entirely — skip the rest of this section for it, and don't run the auth
rubric on a tool that no longer exists in the design. If the outcome is
"alternative-approach" or "declined — degraded," keep the tool in the
inventory (renamed to reflect what it now actually does, e.g. "check
flight status" via a browsing tool instead of "flight status API"), note
the accepted tradeoff, and continue the rubric below as normal — an
alternative-approach tool still needs its own read/write and auth-tier
decision like any other tool.

Custom tools skip sourcing entirely — go straight to the rubric.

### 3. For every remaining tool, run the same per-tool rubric, batched

For each tool that's either custom or externally-sourced-and-kept, ask
(or infer with a stated recommendation the user confirms):

1. **Read or write?** *(read-only / mutating)*
2. **If mutating: is the action reversible (can be undone cleanly) or
   irreversible (money moved, message sent, record deleted)?**
   *(reversible / irreversible — irreversible mutating tools are exactly
   what stage 1's high-impact flag was watching for; if this tool is
   irreversible and stage 1 said "no" to high-impact, surface that
   mismatch now.)*
3. **Who/what authorizes this call?** *(the calling user's existing
   permissions, a separate service-account scope narrower than the user's,
   or a required human-approval step before it fires)* — recommend
   human-approval for any irreversible mutating tool unless the user gives
   a specific reason it's safe to automate fully.
4. **Does this tool need to be idempotent (safe to call twice with the
   same input, e.g. on a retry)?** *(yes/no — recommend yes for any
   mutating tool that sits behind a retryable step, which is most of
   them.)*
5. **Does this call need to be individually audit-logged (who/what/when,
   queryable later)?** *(yes/no — recommend yes for every mutating tool,
   no for pure read-only lookups unless compliance says otherwise.)*

### 4. Apply a deterministic authorization tier per tool

- Read-only → **no gate**, standard access-scoped auth only.
- Mutating, reversible, no compliance flag → **service-scoped auth,
   idempotent, logged** — no human approval required.
- Mutating, irreversible, or stage 1 flagged high-impact → **human
  approval required before execution**, idempotent, individually audited
  — this is the same non-negotiable rule stage 1's ground rules already
  established; this stage is where it becomes a concrete per-tool gate
  instead of an abstract flag.

### 5. Write `system_design/04_tools_and_authorization.md`

```markdown
# Stage 4: Tools & Authorization Boundary

## Tool inventory

| Tool | Sourcing | Read/Write | Reversible? | Auth tier | Idempotent? | Audited? |
|---|---|---|---|---|---|---|
| <name> | Custom / Free / Paid-approved / Alternative-approach / Declined-degraded / Declined-omitted | ... | ... | ... | ... | ... |

## External tool sourcing decisions
<one block per external tool, pasted from
agent-decision-external-tool-sourcing's returned record — researched
options with sources, the decision, and the exact capability impact if
declined or degraded. Omit this section only if every tool in the
inventory is custom.>

## Per-tool rationale
<for each tool, one line citing the specific answer that set its auth
tier — especially any tool routed to "human approval required">

## Mismatches surfaced (if any)
<e.g. "issue_refund is irreversible but stage 1's high-impact flag was
'no' — flagging this back to the user rather than silently deciding">

## Carried-forward signals for later stages
- Tools requiring an audit trail: <list> (feeds stage 5 memory's audit
  history category)
- Tools requiring human-approval state (pending/approved/rejected) to be
  tracked: <list> (feeds stage 5's task-state category and stage 7's loop
  interrupt points)
- Capabilities declined or degraded due to external tool cost: <list,
  each with its exact stated impact from the sourcing decision — later
  stages (memory, loop engineering, eval) must design around the agent
  actually lacking or having a limited version of this capability, not
  assume it exists as originally scoped>

## Status: PENDING APPROVAL
```

### 6. Stop and get explicit approval

Same discipline as prior stages — especially don't let a mutating,
irreversible tool slip through without the user explicitly confirming its
auth tier.

## Ground rules

- Never assign "no human approval required" to an irreversible mutating
  tool by default — that decision must be an explicit, stated exception,
  not an omission.
- Never merge distinct actions into one vague "tool" — granular tools with
  individually correct auth tiers beat one coarse tool with one
  compromise tier.
- If this stage's findings contradict stage 1's high-impact flag (in
  either direction), surface it explicitly rather than silently
  reconciling it — the user may need to revisit stage 1.
- Never skip `agent-decision-external-tool-sourcing` for a tool that
  calls a third-party service, and never assume its outcome — always
  invoke it and use its actual returned record, even if a similar tool
  was sourced earlier in the same session (pricing/free-tier terms can
  differ per capability, and re-using a stale answer defeats the point of
  researching it fresh).
- Never silently drop a "declined — omitted" tool from the design without
  the capability-loss statement and carried-forward signal appearing in
  this stage's output file — a later stage must be able to see it was
  removed and why, not just discover a gap.
