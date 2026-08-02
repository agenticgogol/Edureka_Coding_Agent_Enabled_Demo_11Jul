---
name: agent-decision-memory
description: Stage 5 of the staged agent-system-design pipeline. Given the usecase and every decision made in stages 1-4 (topology, pattern, runtime shape, tools), decides what memory is needed per category and how it's stored. Writes system_design/05_memory.md and stops for explicit user approval.
---

# Agent Decision: Memory & State Design

Stage 5 of `/agent-system-design`. Decides, per memory category, whether
it's needed at all and if so how it's stored, scoped, and expired. Reads
stages 1-4 as fixed inputs — the runtime shape (stage 3) determines
whether state must be durable, and the tool inventory (stage 4) determines
what task-state and audit-history actually need to hold.

Grounded in the six-category taxonomy used across this repo's teaching
material (`teaching/langgraph_basics/agent_memory_deepdive.ipynb`):
conversation context, user preferences, task/scratch state, business
records, long-term knowledge, audit history.

## When to use

- Called by `/agent-system-design` as stage 5, after stage 4's tool
  inventory is approved.
- Requires stages 1-4 at `Status: APPROVED`.

## Input

- Usecase + clarifying answers.
- Approved topology, pattern, runtime shape, and tool inventory from
  stages 1-4, specifically: the persisted-state requirement from stage 3,
  and the audit-trail / approval-state requirements from stage 4.

## Procedure

### 1. Walk each of the six categories, batched with recommendations

For each category, ask: is this needed for this usecase, and if so, what
store type and scope?

1. **Conversation context** — the current turn/session's dialogue history.
   *(needed for anything interactive; not needed for a pure batch/event
   job with no back-and-forth)* Store: in-context (fits in the prompt) vs.
   externally stored and reloaded per turn. Scope: per-session.

2. **User preferences** — durable facts about how a specific user wants
   things done, that should persist across sessions.
   *(needed if the same user returns and expects continuity; not needed
   for one-shot or anonymous usage)* Store: key-value or small
   structured record. Scope: per-user, long TTL.

3. **Task/scratch state** — intermediate work-in-progress for the current
   task (plan steps, tool call results not yet finalized, human-approval
   pending/approved/rejected status from stage 4).
   *(needed whenever stage 3 flagged persisted/checkpointed state, or
   stage 4 flagged tools with a human-approval gate)* Store: must match
   stage 3's durability requirement — if stage 3 said durable, this must
   be an externally persisted, checkpointed store, not in-memory only.
   Scope: per-task-instance, expires on task completion.

4. **Business records** — the actual domain data the agent reads/writes
   (accounts, tickets, orders) — usually not new infrastructure, it's
   whatever system of record already exists.
   *(almost always needed if there are any tools at all from stage 4)*
   Store: existing database/API of record, not duplicated into
   agent-specific storage.

5. **Long-term knowledge** — facts, docs, or policies the agent needs to
   reference that change over time (this is RAG territory if stage 2
   already chose a RAG-flavored pattern).
   *(needed if stage 2's Q1 in the single-agent branch said "changing
   documents/policies")* Store: vector store or search index, matching
   whatever stage 2 already implied — don't re-decide the pattern here,
   just confirm the storage layer.

6. **Audit history** — an immutable log of what the agent did and why,
   especially for tools stage 4 flagged as requiring an audit trail.
   *(needed whenever stage 4 lists any audited tools)* Store: append-only
   log, separate from task/scratch state so it survives past task
   completion. Scope: long retention, matching compliance need if any.

### 2. Apply the decision logic

For each category: **not needed** (state why — e.g. "no return users, so
no preferences category"), or **needed**, with store type and scope
explicitly named. Cross-check category 3 and 6 directly against stages
3 and 4's carried-forward signals — don't leave them freestanding.

### 3. Write `system_design/05_memory.md`

```markdown
# Stage 5: Memory & State Design

## Per-category decisions

| Category | Needed? | Store type | Scope / TTL | Rationale |
|---|---|---|---|---|
| Conversation context | ... | ... | ... | ... |
| User preferences | ... | ... | ... | ... |
| Task/scratch state | ... | ... | ... | ... |
| Business records | ... | ... | ... | ... |
| Long-term knowledge | ... | ... | ... | ... |
| Audit history | ... | ... | ... | ... |

## Cross-checks against stages 3-4
<confirm task/scratch state's durability matches stage 3; confirm audit
history covers every tool stage 4 flagged as audited>

## Status: PENDING APPROVAL
```

### 4. Stop and get explicit approval

## Ground rules

- Never invent a memory category's need independent of stages 1-4's
  actual signals — e.g. don't add durable task-state storage if stage 3
  explicitly said synchronous, non-durable is sufficient.
- Never let long-term knowledge storage silently re-decide stage 2's
  pattern choice — if stage 2 didn't choose RAG, don't introduce a vector
  store here without flagging the inconsistency back to the user.
- Business records (category 4) should default to "reuse the existing
  system of record" — flag it as a real decision only if the usecase
  genuinely has no existing store to read/write.
