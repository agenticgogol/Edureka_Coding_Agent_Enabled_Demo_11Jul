---
name: agent-decision-eval-security-guardrails
description: Stage 8 of the staged agent-system-design pipeline. Given the usecase and all decisions made in stages 1-7, decides what AI evaluation, agent security, guardrails, and observability the system needs, plus cost/latency budgets. Writes system_design/08_eval_security_guardrails.md and stops for explicit user approval.
---

# Agent Decision: Eval, Security, Guardrails & Observability

Stage 8 of `/agent-system-design`, the last decision stage before
assembly. Four sub-rubrics that share the same risk inputs from earlier
stages — tool write-access (stage 4), untrusted content in context (stage
6), and volume/latency/cost ceilings (stage 3) — so they're decided
together in one pass rather than as separate gated stages.

## When to use

- Called by `/agent-system-design` as stage 8, after stage 7's loop
  engineering is approved.
- Requires stages 1-7 at `Status: APPROVED`.

## Input

- Usecase + clarifying answers.
- Approved decisions from all prior stages — specifically stage 4's tool
  authorization tiers, stage 6's untrusted-content flag, and stage 3's
  volume/latency/cost signals.

## Procedure

### 1. Security sub-rubric

1. **For every tool stage 4 marked mutating: is there a plausible
   prompt-injection or tool-injection path where untrusted input
   (retrieved doc, tool output, user message) could cause that tool to
   fire with attacker-controlled arguments?** Walk stage 4's tool table
   and stage 6's untrusted-content flag together — if stage 6 said "yes,
   untrusted content enters context" and any stage 4 tool is mutating,
   this is a real surface, not hypothetical.
2. **Does any tool construct a query (SQL, shell, API call) from
   model-generated input directly, or is it parameterized/allow-listed?**
   *(direct-construction (risk) / parameterized-or-allowlisted (safe) —
   recommend parameterized as the required default for any tool touching
   a database or shell.)*
3. **Is there a clear auth boundary per tool matching stage 4's tiers, or
   could any tool be called with more privilege than its tier implies?**

Recommend running `security-check` against the actual implementation once
code exists — this stage decides *what* to check for, `security-check`
verifies the built code against it.

### 2. Guardrails sub-rubric

4. **What input guardrails are needed?** *(reject/flag off-topic requests,
   PII detection before it reaches a tool, jailbreak/injection pattern
   filtering — recommend based on stage 6's untrusted-content answer and
   the usecase's data sensitivity.)*
5. **What output guardrails are needed?** *(refuse to state the mutating
   tools' results as final without the stage 7 human-approval interrupt
   having actually fired, tone/compliance filtering, structured-output
   schema validation before returning to the caller.)*
6. **What's the guardrail failure behavior — block silently, block with a
   user-visible message, or degrade to a safer fallback response?**
   *(recommend a user-visible, honest message over silent blocking, so
   failures are debuggable rather than mysterious.)*

### 3. Evaluation sub-rubric

7. **What does "good enough to ship" mean for this usecase, concretely?**
   *(a golden set of representative inputs with expected outputs/behavior
   — size should match the risk level: higher for anything stage 4 flagged
   high-authorization.)*
8. **What judges the output — an exact-match/rule-based check, an
   LLM-as-judge, or human review of a sample?** *(recommend rule-based
   wherever the output has a checkable structure; LLM-judge only where
   correctness is genuinely subjective; human review as a supplement for
   the highest-risk tool paths, not a replacement for the other two.)*
9. **What's the re-eval trigger?** *(every deploy / on a schedule / on a
   prompt or tool change — recommend "every deploy plus on any prompt/tool
   change," matching `eval-and-observability`'s existing default.)*

### 4. Observability sub-rubric (distinct from eval — continuous, not periodic)

10. **What gets traced per invocation?** *(every LLM call and tool call
    with latency/token/cost, the full step sequence for multi-step loops,
    which interrupt points from stage 7 actually fired) — recommend
    tracing every call at minimum; full step sequence for anything stage
    2 chose as a looping pattern.)*
11. **What triggers an alert, as opposed to just being logged?**
    *(step-ceiling hit rate exceeding a threshold, human-approval queue
    backing up, cost-per-request drifting above stage 3's ceiling, error
    rate on any mutating tool — pick the ones concretely relevant to this
    usecase's real risk, not a generic list.)*
12. **What's the tracing backend?** *(reuse whatever this
    repo/org already has via `eval-and-observability`'s Phoenix/local
    fallback default, unless the usecase has an existing stack to
    integrate with instead.)*

### 5. Cost/latency budget (carried forward, confirmed here)

13. Restate stage 3's volume/latency/cost ceiling and confirm the chosen
    pattern (stage 2), runtime shape (stage 3), and model choices (stage
    2's notes) are actually consistent with it — if the design as
    assembled would clearly blow the budget (e.g. a multi-agent
    supervisor pattern at a cost ceiling that only supports single-model
    calls), surface that conflict now rather than at assembly.

### 6. Write `system_design/08_eval_security_guardrails.md`

```markdown
# Stage 8: Eval, Security, Guardrails & Observability

## Security
<injection surfaces identified, query-construction safety, auth-boundary
confirmation — reference stage 4's tool table directly>

## Guardrails
<input guardrails, output guardrails, failure behavior>

## Evaluation
<golden set description, judge type, re-eval trigger>

## Observability
<what's traced, alert conditions, backend>

## Cost/latency budget check
<stage 3's ceiling restated, and confirmation or flagged conflict against
the assembled design>

## Status: PENDING APPROVAL
```

### 7. Stop and get explicit approval

## Ground rules

- Never treat eval and observability as one item — eval is periodic/
  offline quality measurement, observability is continuous production
  monitoring; both need explicit answers.
- Any tool stage 4 marked mutating, combined with stage 6's
  untrusted-content flag being "yes," is a mandatory security finding here
  — don't let it pass silently as "no injection risk identified."
- If the cost/latency check in step 5 surfaces a real conflict, don't
  resolve it unilaterally — send the user back to the relevant earlier
  stage (usually stage 2 or 3) rather than quietly picking a cheaper model
  to make the budget work.
