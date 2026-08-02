---
name: agent-decision-design-pattern
description: Stage 2 of the staged agent-system-design pipeline. Given a usecase, clarifying answers, and the single-vs-multi decision already made in stage 1, decides the specific design pattern to use. Writes system_design/02_design_pattern.md and stops for explicit user approval.
---

# Agent Decision: Design Pattern Selection

Stage 2 of `/agent-system-design`. Takes the single-agent/multi-agent
decision from `system_design/01_agent_topology.md` as a **fixed input** —
never re-litigate it here — and picks the specific execution shape within
that branch.

## When to use

- Called by `/agent-system-design` as stage 2, after
  `agent-decision-single-vs-multi` has an approved output.
- `system_design/01_agent_topology.md` must exist with `Status: APPROVED`
  before this stage runs. If it doesn't, stop and say so — don't guess the
  topology from context.

## Input

- Usecase + clarifying answers (carried from stage 0).
- `system_design/01_agent_topology.md`: the topology decision, the
  bounded/decomposition sub-branch signal (if single-agent), and the
  high-impact/irreversible flag.

## Procedure

### 1. Branch on stage 1's decision

**If single-agent:**

Ask, batched with recommendations:

1. **What's the dominant knowledge requirement?**
   *(exact live business data via a database/API / changing documents or
   policies that need citation / stable tone or behavior, not facts / no
   external knowledge needed)*
2. **Given stage 1's sub-branch signal, confirm: bounded tool loop, or
   explicit up-front plan decomposition?** *(only ask if stage 1 left this
   ambiguous — usually it's already answered.)*

Apply:
- Q1 = "no external knowledge" + no dynamic branching needed →
  **deterministic code** (no LLM agent loop at all — say so plainly, this
  is the cheapest correct answer and newcomers often skip past it).
- Q1 = "changing documents," steps known → **RAG assistant, fixed
  workflow** (retrieval + generation, no agent loop).
- Steps known, some LLM interpretation but no dynamic tool use →
  **fixed workflow** (deterministic graph, LLM used for a bounded
  step, not a loop).
- Steps dynamic, bounded tool space → **bounded ReAct agent**.
- Steps dynamic, needs up-front decomposition → **planner-executor**.

**If multi-agent:**

Ask, batched with recommendations, framed the same way as the
`09_architecture_selection_capstone.ipynb` cheat sheet
(`teaching/langgraph_basics/multi_agent_architectures/`):

1. **Are the sub-tasks independent of each other (can run in any order /
   concurrently), or does each step depend on what a previous step
   found?** *(independent / dependent)*
2. **Is there a real, distinct set of specialist domains to route
   between (e.g. billing vs. infra vs. account), or is it one process
   with a second role that double-checks the first?**
   *(specialist-domains / single-process-with-checker / neither)*
3. **Does the routing/hierarchy itself have more than one level (e.g. a
   region-level split, each with its own specialist split underneath), or
   is one level of routing enough?** *(one level / multiple levels)*
4. **Do two or more roughly-equal peer roles need to hand off directly to
   each other without a central dispatcher?** *(no / yes)*
5. **Is there a mutating/consequential decision that a compliance or
   safety requirement says must be independently re-verified by a
   different reasoning pass before it takes effect?** *(no / yes — carries
   forward from stage 1's high-impact flag if that was "yes.")*

Apply, in priority order (matches the capstone's real evidence):
- Q1 = independent → **parallel fan-out/fan-in**.
- Q1 = dependent, Q5 = yes, Q2 = single-process-with-checker →
  **critic-actor (evaluator-optimizer)**.
- Q2 = specialist-domains, Q3 = one level → **supervisor
  (orchestrator-worker)**.
- Q2 = specialist-domains, Q3 = multiple levels → **hierarchical
  supervisor-of-supervisors**.
- Q4 = yes → **peer-to-peer (network) handoff**.
- Q1 = dependent, fixed known order, no specialist split →
  **sequential pipeline**.

Always name the 1-2 next-simplest alternatives rejected and the specific
answer that ruled each out — e.g. "parallel fan-out/fan-in rejected: Q1 =
dependent, not independent."

### 2. Note model/provider selection inline, don't gate on it

If the usecase has an obvious per-role cost/quality split (e.g. a cheap
model for routing, a stronger model for the final answer), note it as a
recommendation inside this stage's output — it's a local decision to the
chosen pattern's nodes, not its own approval gate.

### 3. Write `system_design/02_design_pattern.md`

```markdown
# Stage 2: Design Pattern

## Topology (from stage 1): Single-Agent | Multi-Agent

## Decision walkthrough
<questions asked and answers given>

## Chosen pattern
<one of the named patterns, plus an ASCII topology diagram specific to
this usecase, not a generic template>

## Rejected alternatives
<1-2 next-simplest patterns, and the specific answer that ruled each out>

## Model/provider notes (non-gating)
<per-role model choice, if the usecase has an obvious split; otherwise "no
split needed, single model">

## Status: PENDING APPROVAL
```

### 4. Stop and get explicit approval

Same discipline as stage 1 — don't proceed to stage 3 until confirmed.

## Ground rules

- Never re-litigate stage 1's topology decision here — if it looks wrong
  in light of stage 2's questions, say so explicitly and send the user
  back to stage 1 rather than silently overriding it.
- Never pick the most sophisticated pattern by default — the recommended
  default at every branch point is the simplest option; a more complex
  pattern needs a specific answer justifying it.
- Ground pattern claims in the repo's own measured evidence
  (`teaching/langgraph_basics/multi_agent_architectures/`,
  `single_agent_architectures/`) where applicable, not folklore.
