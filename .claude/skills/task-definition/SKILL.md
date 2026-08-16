---
name: task-definition
description: MUST USE whenever the user wants to define, list, scope, or start an eval for an agent — "let's eval this agent", "what tasks should we test", "build an eval suite", "eval/tasks.md", or any mention of evaluating agent behavior before a golden set or metrics exist. This is always the FIRST eval-toolkit skill to run; produces eval/tasks.md. Trigger eagerly — do not wait for the user to say "task definition" explicitly.
---

# Task Definition

Produces `eval/tasks.md`: the canonical list of tasks the agent under evaluation must handle, prioritized, and confirmed by the user.

## Steps

1. **Load agent context.** Read `eval/state.md` if it exists — it should describe the agent's purpose, tools, inputs/outputs, and domain. If `eval/state.md` is absent, ask the user directly for: what the agent does, what tools/APIs it calls, what a typical user request looks like, and any known failure modes. Do not proceed on assumptions.

2. **Scan for task shapes.** Using the agent context, identify which of these shapes plausibly apply, and draft 1-3 concrete tasks per shape that fits:
   - **direct-answer** — single-turn Q&A, no tools needed
   - **multi-intent** — one user message bundling multiple requests
   - **tool-invocation** — task requires calling one or more tools/APIs correctly
   - **escalation/handoff** — agent must recognize when to hand off to a human or another system
   - **policy-bound** — task constrained by business rules, compliance, or refusal conditions
   - **multi-turn/stateful** — behavior depends on conversation history or session state
   - **edge/adversarial** — malformed input, prompt injection, out-of-scope requests
   - **error-recovery** — tool failure, empty results, or bad upstream data that the agent must recover from gracefully

   Skip shapes that clearly don't apply to this agent — do not force-fit all eight.

3. **Present the draft list for editing — PAUSE HERE.** Show the user the full candidate task list before writing anything to disk. Explicitly invite them to add, delete, merge, or reprioritize entries. Do not write `eval/tasks.md` until the user confirms the list is final. Never auto-approve on the user's behalf, even if the draft looks obviously reasonable.

4. **Write `eval/tasks.md`** as a table once approved:

   | ID | Task | Description | Priority |
   |----|------|-------------|----------|
   | T1 | ... | ... | P0/P1/P2 |

   Use `T{n}` IDs, stable across future edits (don't renumber on later additions — append or mark deprecated instead).

## Rules

- Never skip the pause-for-editing step, regardless of how confident the draft looks.
- Priority should reflect real usage frequency/risk, not just shape coverage — ask the user if unclear.
- If `eval/tasks.md` already exists, show the existing table first and ask whether this is a revision or a fresh pass — don't silently overwrite.
