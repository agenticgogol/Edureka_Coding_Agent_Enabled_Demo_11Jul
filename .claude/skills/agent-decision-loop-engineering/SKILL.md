---
name: agent-decision-loop-engineering
description: Stage 7 of the staged agent-system-design pipeline. Given the usecase and decisions made in stages 1-6, decides the agent's control-flow loop — step ceilings, termination conditions, retry policy, and human-in-the-loop interrupt points. Writes system_design/07_loop_engineering.md and stops for explicit user approval.
---

# Agent Decision: Loop Engineering

Stage 7 of `/agent-system-design`. Decides how the agent's execution loop
actually terminates, retries, and pauses for humans — the control-flow
discipline that keeps a dynamic agent (stage 1/2's bounded ReAct or
planner-executor branches, or any multi-agent role with its own loop) from
running away. Grounded in
`teaching/langgraph_basics/loop_engineering/`.

If stage 2 chose deterministic code or a fixed workflow with no agent
loop at all, this stage still runs but is short — most questions collapse
to "not applicable, there's no dynamic loop," and that should be stated
explicitly rather than skipping the stage.

## When to use

- Called by `/agent-system-design` as stage 7, after stage 6's context
  engineering is approved.
- Requires stages 1-6 at `Status: APPROVED`.

## Input

- Usecase + clarifying answers.
- Approved decisions from stages 1-6, especially: whether stage 2 chose a
  looping pattern at all, stage 4's tools requiring human approval, and
  stage 3's runtime durability.

## Procedure

### 1. Ask the loop rubric, batched with recommendations

1. **What's the maximum number of steps/tool calls a single task should
   ever take before it's forced to stop and either finalize or escalate?**
   *(a concrete number, not "as many as needed" — recommend starting from
   the smallest ceiling that covers the usecase's real worst case observed
   or estimated, not an arbitrarily large safety margin.)*

2. **What are the legitimate termination conditions — the ways the loop is
   supposed to end successfully?** *(task's goal condition met / plan
   exhausted with a final answer produced / explicit "I can't determine
   this" fallback — enumerate all of them; an agent with only one
   recognized success condition tends to force a low-confidence answer
   through it rather than admitting uncertainty.)*

3. **On a tool failure or malformed output, what's the retry policy?**
   *(no retry, fail immediately / fixed number of retries with backoff /
   retry with a corrected prompt reflecting the specific error — recommend
   a small fixed retry count with backoff for transient tool failures, and
   a single corrected-prompt retry for malformed-output failures, not
   unbounded retries.)*

4. **Where does the loop need to pause and wait for a human, based on
   stage 4's tool authorization tiers?** *(list every tool stage 4 marked
   "human approval required" — each one is a mandatory interrupt point in
   the loop, not optional.)*

5. **What happens if the step ceiling (Q1) is hit without a legitimate
   termination condition (Q2) being met?** *(escalate to a human with the
   partial state / return a explicit "could not complete" rather than a
   best-effort guess / hard fail — recommend explicit escalation or honest
   incompleteness over silently returning a low-confidence final answer as
   if it were complete.)*

6. **For planner-executor or supervisor patterns (if chosen in stage 2):
   under what condition does the plan get revised mid-execution
   (replanning), and is there a cap on how many times a single task can be
   replanned?** *(only ask if applicable — not applicable for bounded
   ReAct or fixed workflows.)*

### 2. Cross-check against stage 4's tool authorization tiers

Every tool marked "human approval required" in stage 4 must appear as an
explicit interrupt point in this stage's output — if it's missing, that's
a gap, not a simplification; surface it before writing the final file.

### 3. Write `system_design/07_loop_engineering.md`

```markdown
# Stage 7: Loop Engineering

## Applicability
<confirm whether stage 2 chose a looping pattern at all; if not, state
"no dynamic loop — this stage's controls are not applicable" and stop
here with a minimal file>

## Step ceiling
<the number, and the reasoning behind it>

## Termination conditions
<enumerated list>

## Retry policy
<per failure type>

## Human-in-the-loop interrupt points
<every tool from stage 4 requiring approval, mapped to the loop step
where the pause occurs>

## Ceiling-exceeded behavior
<escalate / explicit incompleteness / hard fail, and why>

## Replanning policy (if applicable)
<trigger condition and cap>

## Status: PENDING APPROVAL
```

### 4. Stop and get explicit approval

## Ground rules

- Never leave the step ceiling unbounded ("as many as needed") — a
  concrete number is required even if it's a rough estimate the user can
  revise later.
- Every human-approval tool from stage 4 must have a corresponding
  interrupt point here — this is a hard cross-check, not a suggestion.
- Never let "ceiling exceeded" default to silently returning a best-effort
  answer — that's exactly the failure mode this stage exists to prevent.
