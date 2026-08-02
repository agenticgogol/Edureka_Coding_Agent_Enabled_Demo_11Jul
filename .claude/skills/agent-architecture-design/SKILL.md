---
name: agent-architecture-design
description: Use when the user wants to build an agent, or is unsure whether they need one, and the underlying system-design pattern hasn't been chosen and justified yet. Interviews the user against Tier 9's decision framework and writes a finalized architecture design document — which of the six patterns (deterministic code, fixed workflow, RAG assistant, bounded ReAct agent, planner-executor, supervisor/multi-agent), why, rejected alternatives, and required overlays (security, guardrails, cost/latency, evaluation).
---

# Agent Architecture Design

Turns "I want to build an agent for X" into a defensible, written architecture
decision — before any framework, any graph, any code. This is the skill that
answers the question Tier 9 is built around: not "LangGraph or something
else," but whether dynamic autonomy is worth its own uncertainty for this
specific problem, and if so, which of six genuinely different execution
shapes actually fits.

Theory and worked examples backing every question below live in
`teaching/langgraph_agent_projects/tier9_agent_architecture_system_design_selection/architecture_reference.html`
(Theory tab for the full reasoning + real precedents, Cheatsheet tab for a
fast-scan version). Read it once if you haven't; this skill applies the same
decision logic interactively, grounded in the user's actual request instead
of a hypothetical.

## When to use

- User says something like "help me build an agent for X," "should this be
  an agent or a workflow," "design an architecture for Y," or opens a new
  project/concept whose brief describes agent-like behavior.
- A `project_brief.md`/`concept_brief.md`/`design.md` already exists but
  assumes an architecture pattern (e.g. "a LangGraph agent") without a
  written justification for why that pattern over a simpler one.
- Someone on the team asks "why did we build this as an agent instead of a
  workflow" and there's no document that answers it.

## When NOT to use

- `design.md` already contains an explicit "Architecture pattern chosen
  because..." section reasoned through this same framework — don't
  re-interview, just point to it.
- The task is unambiguously a single deterministic transformation (classify
  one field, format one output) with no agent framing anywhere in the
  request — that's Module 1's gate resolving itself; no interview needed,
  just say so and recommend `technical-design` directly with a plain
  function/prompt call.

## How this composes with the rest of the repo's workflow

This skill runs **before or alongside `clarify-requirements`**, specifically
to resolve the architecture-pattern question — `clarify-requirements` still
needs to run for everything else a brief leaves open (providers, data
shapes, non-goals). Once this skill's design document exists:

1. If a `project_brief.md`/`concept_brief.md` doesn't exist yet, offer to
   draft one via `write-project-brief`/`write-concept-brief` first — the
   interview below still applies, it just informs that brief's architecture
   section instead of standing alone.
2. Feed the finalized architecture pattern and its overlays directly into
   `technical-design` as a resolved input — `design.md`'s "Tech choices and
   why" section should cite this document rather than re-deciding the
   pattern from scratch.
3. For the framework-specific build step (`agent-langgraph`,
   `agent-crewai`, etc.), this document is what tells you *which* pattern
   to implement — a bounded agent, a planner-executor, a supervisor — not
   just that "an agent" is being built.

## Procedure

### 1. Establish the business problem first, in the user's own words

Before any multiple-choice question, ask in plain language (this part is
genuinely open-ended, no options apply):
- What's the business outcome, and what happens today without this system?
- Who hits "wrong" or "too slow" here, and what does that actually cost
  them (a wrong answer, a missed SLA, money, safety)?

Don't skip this even if the user already described a technical shape
("build a LangGraph agent that...") — restate their technical framing back
as a hypothesis, not a given, and confirm the underlying business need
matches it. A user asking for "an agent" is describing a solution, not
necessarily a requirement; this skill's job is to check that solution
against the actual problem before building it.

### 2. Run the interview as one batched, numbered set of concrete-option questions

Mirror `clarify-requirements`' style exactly: every question that has a
defensible default gets 2-4 concrete options plus a recommendation, so the
user can answer with a word, not a paragraph. Ask all of these in one
message, grouped by module (matching the reference doc's structure):

**Module 1 — Is an agent justified?**
1. Are the steps mostly known in advance, or does the sequence genuinely
   vary based on what's discovered mid-task? *(known / dynamic — recommend
   "known" unless the user can name a specific case where the next step
   can't be predicted ahead of time)*
2. Can the output change a person's money, access, health, employment, or
   legal status, or take an irreversible action? *(no / yes — if yes, this
   alone routes toward human-governed design regardless of other answers)*

**Module 3 — Knowledge need**
3. What's the dominant knowledge requirement? *(exact live business
   data via a database/API / changing documents or policies that need
   citation / stable tone or behavior, not facts / no external knowledge
   needed)*

**Module 2 — Autonomy shape** *(skip if Q1 was "known")*
4. If dynamic: is the tool/step space small enough to bound with an
   allowlist and a step ceiling, or does the task need explicit up-front
   decomposition into dependent subtasks before execution? *(bounded
   single agent / planner-executor — recommend bounded single agent unless
   subtasks have real dependencies on each other's output)*
5. Do genuinely different specialist capabilities need independent
   execution with typed handoffs, where parallelism or isolation would
   measurably beat one agent doing everything? *(no / yes — recommend "no"
   by default; multi-agent's coordination cost is only worth it for
   measurably parallelizable work, not general sophistication)*

**Module 5 — Workload shape**
6. What's the workload shape? *(short interactive request / long-running
   or restartable work / high-volume batch / triggered by a business
   event / requires a human review step)*

**Scale and constraints**
7. Expected volume (requests/day, order of magnitude) and any hard latency
   SLO or budget ceiling already set by the business?
8. Any existing stack/team constraints (must reuse an existing framework,
   team's LangGraph experience level, existing observability stack)?

### 3. Apply the decision logic deterministically, and show your work

Walk through the same logic as the reference doc's overview table, in this
priority order (don't let a later question override an earlier one that
already forced a decision):

1. Q2 = yes (high-impact/irreversible) → **human-governed decision
   system**, regardless of other answers — the agent/workflow underneath it
   still gets chosen via the rest of this list, but a mandatory approval
   gate wraps it.
2. Q6 = long-running/batch/event-driven → **durable async/event workflow**
   as the runtime shape, with the control-flow pattern chosen independently
   via Q1/Q4/Q5.
3. Q3 = changing documents, Q1 = known → **RAG assistant with a fixed
   workflow**, no agent loop.
4. Q5 = yes → **supervisor–specialists (multi-agent)**.
5. Q1 = dynamic, Q4 = bounded → **bounded ReAct agent**.
6. Q1 = dynamic, Q4 = decomposition → **planner–executor**.
7. Otherwise (Q1 = known, no other override) → **deterministic code or
   fixed workflow** — recommend the least complex of the two based on
   whether any LLM interpretation step exists at all.

State the chosen pattern, then explicitly name the 1-2 next-simplest
alternatives that were considered and why they were rejected — this is
load-bearing, not a formality: a design that doesn't name what it rejected
looks identical whether the simpler option was actually considered or
never occurred to anyone.

### 4. Write `architecture_design.md`

Place it next to the project/concept brief if one exists
(`projects/<slug>/architecture_design.md` or
`concepts/<slug>/architecture_design.md`), otherwise in the current working
directory. Structure:

```markdown
# Architecture Design: <Name>

## Business outcome
<what happens today, what this changes, how success is measured>

## Decision walkthrough
<each interview question and the answer given, in order — this is the
audit trail for why the pattern below was chosen, not just a summary>

## Chosen architecture pattern
<one of: deterministic code / fixed workflow / RAG assistant / bounded
ReAct agent / planner-executor / supervisor-specialists / human-governed
decision system (as a wrapper around one of the above) — plus the ASCII
topology diagram for this specific system, not a generic one>

## Rejected alternatives
<the 1-2 next-simplest patterns considered, and the specific answer above
that ruled each one out>

## Knowledge & state design
<per Module 3's taxonomy: which of transactional-tool / RAG / fine-tuning
/ curated-context this system needs, and which of the six memory
categories apply — conversation context, preferences, task state,
business records, long-term knowledge, audit history>

## Tool & side-effect boundaries
<per Module 4: for every tool this system needs, read vs. write, what
authorizes it, idempotency/audit/approval requirements for writes>

## Runtime & deployment shape
<per Module 5: synchronous / async / batch / event-driven / durable,
matched to the workload-shape answer, with required controls>

## Non-functional budgets & overlays
<explicit numbers where the user gave them (volume, latency SLO, cost
ceiling); which of Tier 6 (security)/Tier 7 (guardrails)/Tier 8
(cost/latency) overlays apply, cross-referencing their reference docs>

## Evaluation & rollout gates
<representative workload shape, quality/safety/cost/latency thresholds,
what "ready to ship" requires>

## Architecture-change triggers
<explicit future signals — volume growth, a new risk category, a
repeated failure mode — that would justify revisiting this decision>
```

### 5. Show the draft, get explicit confirmation, then hand off

Don't treat the document as final until the user confirms the chosen
pattern and rejected alternatives actually match their intent — the same
discipline `clarify-requirements` applies to briefs generally. Once
confirmed, recommend `technical-design` next (or `write-project-brief`
first, if no brief exists), explicitly pointing it at this document's
"Chosen architecture pattern" and "Non-functional budgets & overlays"
sections as resolved inputs rather than open questions.

## Ground rules

- Never infer the architecture pattern from a one-line request without
  running the interview — "build me an agent that does X" is a starting
  hypothesis, not a resolved design; guessing the pattern defeats the
  entire point of this skill.
- Never let "the user asked for an agent" override Q2's answer — if the
  action is high-impact or irreversible, the human-governance wrapper is
  non-negotiable regardless of what the user initially asked for, though
  you should say so explicitly rather than silently overriding their
  request.
- Always name rejected alternatives with the specific answer that ruled
  each one out — "we considered a bounded agent but the task needs
  cross-specialist parallelism (Q5 = yes)" is the standard; "we considered
  other options" is not.
- If the user's answers are internally inconsistent (e.g. Q1 = "known" but
  they also describe needing to discover tools dynamically), surface the
  conflict and ask rather than picking one silently.
