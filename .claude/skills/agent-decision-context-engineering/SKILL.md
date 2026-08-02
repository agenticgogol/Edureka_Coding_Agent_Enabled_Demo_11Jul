---
name: agent-decision-context-engineering
description: Stage 6 of the staged agent-system-design pipeline. Given the usecase and decisions made in stages 1-5 (topology, pattern, runtime, tools, memory), decides what surfaces into the model's context window, from where, and how it's pruned. Writes system_design/06_context_engineering.md and stops for explicit user approval.
---

# Agent Decision: Context Engineering

Stage 6 of `/agent-system-design`. Memory (stage 5) decided what's stored
and where. This stage decides the separate question: of everything that
*could* be pulled into a given LLM call, what actually goes into the
prompt, from which source, in what order, and how it's kept from growing
unbounded. Grounded in
`teaching/langgraph_basics/agent_context_engineering.ipynb`.

## When to use

- Called by `/agent-system-design` as stage 6, after stage 5's memory
  design is approved.
- Requires stages 1-5 at `Status: APPROVED`.

## Input

- Usecase + clarifying answers.
- Approved decisions from stages 1-5, especially the memory category
  table from stage 5 (context engineering decides what *surfaces*, not
  what's *stored* — don't re-decide storage here).

## Procedure

### 1. Ask the context rubric, batched with recommendations

1. **What must always be in the system prompt, regardless of task state?**
   (role/instructions, tool schemas, safety/guardrail boilerplate from
   stage 8 if already known, non-negotiable business rules) — this is
   usually small and fixed; the risk is letting it grow over time as
   edge cases get patched in as prompt text instead of code.

2. **Of stage 5's memory categories, which get pulled into every call
   verbatim, which get pulled only on demand (via a tool/retrieval call),
   and which never enter the model's context directly at all (e.g. raw
   business records too large to inline, summarized instead)?**
   *(always-in-context / on-demand-via-tool / never-direct — recommend
   "on-demand" as the default for anything except conversation context and
   user preferences, which are usually small enough to always include.)*

3. **As the conversation/task grows, what's the pruning strategy once
   context approaches the model's practical limit?**
   *(sliding window (drop oldest turns) / rolling summarization (compress
   old turns into a running summary) / structured note-taking (agent
   writes durable notes to task/scratch state instead of relying on raw
   history) / no pruning needed (task is bounded and short by
   construction) — recommend structured note-taking for multi-step agents
   with task/scratch state already in stage 5's design, sliding window
   for simple chat-only usecases.)*

4. **For multi-agent topologies (if stage 1 = multi-agent): does each
   role get its own separate, narrow context, or does the full history
   flow through every role?**
   *(separate/narrow per role — recommend this as the default; it's what
   this repo's own multi-agent measurements show keeps per-call context
   size down and avoids one role's noise leaking into another's
   reasoning.)*

5. **Is there any untrusted content entering context (retrieved documents,
   tool outputs, user-uploaded files) that needs to be clearly delimited
   from trusted instructions?** *(no / yes — carry forward to stage 8's
   security sub-rubric; this is a prompt-injection surface, not just a
   formatting question.)*

### 2. Apply the decision logic and write it as a concrete map

Don't leave this abstract — produce an explicit table of "what's in
context, at what point in the flow, from what source."

### 3. Write `system_design/06_context_engineering.md`

```markdown
# Stage 6: Context Engineering

## Always-in-context (system prompt / fixed preamble)
<list>

## On-demand context (pulled via tool/retrieval when needed)
<list, mapped to stage 5's memory categories>

## Never-direct (summarized or referenced, not inlined)
<list, and how it's summarized instead>

## Pruning / compaction strategy
<chosen strategy and why, referencing task length/stage 3's runtime shape>

## Per-role context isolation (if multi-agent)
<confirm narrow-per-role vs. shared, and why>

## Untrusted-content delimitation
<yes/no, and if yes, how it's marked and what stage 8 needs to check>

## Status: PENDING APPROVAL
```

### 4. Stop and get explicit approval

## Ground rules

- Never re-decide what's stored (that's stage 5's job) — only decide what
  surfaces into a given call and when.
- Default to on-demand/narrow context over "just include everything" —
  the recommended default at every branch point is the option that keeps
  context smallest, with a stated reason required to expand it.
- If untrusted content enters context, this must be flagged forward to
  stage 8 explicitly — don't let it silently disappear between stages.
