---
name: agent-decision-single-vs-multi
description: First stage of the staged agent-system-design pipeline. Given a usecase and clarifying answers, decides single-agent vs. multi-agent before any pattern is picked. Writes system_design/01_agent_topology.md and stops for explicit user approval before the next stage runs.
---

# Agent Decision: Single-Agent vs. Multi-Agent

This is stage 1 of the `/agent-system-design` pipeline. It answers exactly
one question — does this problem need more than one agent at all — and
stops. It does not pick a specific pattern (bounded ReAct vs.
planner-executor vs. supervisor); that's stage 2's job
(`agent-decision-design-pattern`), which reads this stage's output as a
fixed input.

This is the newcomer-facing, single-question version of Module 1+2 from
`agent-architecture-design`. If the user wants the fast, one-shot version
of the whole pipeline instead of the staged/approved version, point them at
`agent-architecture-design` directly.

## When to use

- Called by `/agent-system-design` as its first stage, after the shared
  clarifying-questions pass.
- Can also be invoked standalone if a user only wants this one decision
  re-litigated (e.g. revising an earlier system design).

## Input

- The usecase description in the user's own words.
- Answers to the shared clarifying questions (business outcome, who is
  affected by a wrong/slow answer, and what that costs).

## Procedure

### 1. Restate the business problem

Before any multiple-choice question, restate the usecase as a hypothesis:
"So the underlying need is X, and you're proposing to solve it with an
agent — let's check that's actually warranted before deciding how many."
Don't skip this even if the user already said "build me a multi-agent
system for..." — that's a solution shape, not a confirmed requirement.

### 2. Ask the topology rubric as one batched, numbered question set

Every question gets 2-4 concrete options plus a recommendation, so a
newcomer can answer with a word:

1. **Are the steps mostly known in advance, or does the sequence genuinely
   vary based on what's discovered mid-task?**
   *(known / dynamic — recommend "known" unless the user can name a
   specific case where the next step can't be predicted ahead of time.
   This is the single most load-bearing question: "known" steps almost
   never need more than one agent, regardless of how many tools exist.)*

2. **Can the output change a person's money, access, health, employment,
   or legal status, or take an irreversible action?**
   *(no / yes — if yes, this doesn't by itself force multi-agent, but it
   forces a human-approval wrapper regardless of the topology answer below,
   and should be carried forward to stage 4 and stage 8.)*

3. **If the steps are dynamic: is the tool/step space small enough to
   bound with an allowlist and a step ceiling, or does the task need
   explicit up-front decomposition into dependent subtasks before
   execution?**
   *(bounded / needs-decomposition — recommend "bounded" unless subtasks
   have real dependencies on each other's output. Both of these are still
   single-agent answers — this question exists to hand stage 2 the right
   sub-branch, not to decide multi-agent.)*

4. **Do genuinely different specialist capabilities need independent
   execution with typed handoffs, where parallelism or isolation would
   measurably beat one agent doing everything?**
   *(no / yes — recommend "no" by default. Multi-agent's coordination cost
   — extra LLM calls for routing/handoff, harder debugging, more failure
   surface — is only worth paying for measurably parallelizable or
   genuinely separable specialist work, not general task sophistication or
   "this feels like it deserves its own agent.")*

5. **Would a wrong answer from one part of the system need to be isolated
   from contaminating the rest (e.g. one customer's data must never leak
   into another's reasoning), in a way a single shared context can't
   guarantee?**
   *(no / yes — a real "yes" here is a second independent signal toward
   multi-agent, distinct from Q4's parallelism argument.)*

### 3. Apply the decision logic deterministically, and show your work

- Q4 = yes, or Q5 = yes → **multi-agent** (the specific pattern is stage
  2's job).
- Otherwise → **single-agent**, and Q3's answer (bounded vs.
  decomposition) is carried forward to stage 2 as the sub-branch signal.
- Q2 = yes is carried forward regardless (human-governance wrapper) — it
  never by itself flips single vs. multi.

State the decision, then explicitly name the rejected alternative and the
specific answer that ruled it out — "single-agent, because Q4 and Q5 were
both no: there's no measurable parallelism or isolation need, just one
continuous task" is the standard. "We considered multi-agent" alone is not
sufficient.

### 4. Write `system_design/01_agent_topology.md`

```markdown
# Stage 1: Agent Topology — Single vs. Multi-Agent

## Business problem (restated)
<the hypothesis confirmed in step 1>

## Decision walkthrough
<Q1-Q5, the answer given to each, in order>

## Decision: Single-Agent | Multi-Agent

## Why
<the specific answer(s) that decided it>

## Rejected alternative
<the other option, and the specific answer that ruled it out>

## Carried-forward signals for later stages
- High-impact/irreversible action: <yes/no, from Q2>
- Sub-branch (if single-agent): bounded | needs-decomposition (from Q3)

## Status: PENDING APPROVAL
```

### 5. Stop and get explicit approval

Show the draft file. Do not proceed to stage 2 until the user confirms
this decision matches their intent. If they want to change an answer,
re-run the affected part of the interview and rewrite the file — don't
patch around it silently.

## Ground rules

- Never infer single vs. multi from a one-line request — "build me a
  multi-agent system" is a starting hypothesis, not a resolved decision.
- Never let general task complexity substitute for Q4/Q5's specific
  answers — "this is a complicated problem" is not evidence of measurable
  parallelism or isolation need.
- Always name the rejected alternative with the specific answer that ruled
  it out.
- If answers are internally inconsistent (e.g. Q1 = "known" but the user
  also describes discovering tools dynamically), surface the conflict and
  ask rather than picking one silently.
