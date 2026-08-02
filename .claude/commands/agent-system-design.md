---
description: Run the full staged agent-system-design pipeline — single-vs-multi, design pattern, runtime shape, tools/authorization, memory, context engineering, loop engineering, then eval/security/guardrails — each stage gated on explicit user approval before the next runs, ending in one assembled architecture_design.md.
argument-hint: <usecase description, or path to an existing project_brief.md/concept_brief.md>
---

This is the newcomer-facing, fully gated version of architecture design.
Unlike `agent-architecture-design` (one-shot interview, one document), this
command runs eight separate decision skills in sequence, each producing its
own file under `system_design/`, and **stops after every single stage for
explicit user approval** before continuing. The whole point is that
someone new to agent system design sees the reasoning and the rejected
alternatives at each individual decision point, not just a finished
document at the end.

Usecase / brief reference: `$ARGUMENTS`

## Sequence

### Stage 0 — Shared clarifying questions (once)

Before any stage-specific skill runs, ask the shared context questions
once, so the same ground isn't re-asked six times:
- The business outcome in plain language: what happens today, who's
  affected by a wrong/slow answer, what that costs.
- Expected volume, any hard latency SLO, any hard cost ceiling already set
  by the business.
- Any existing stack/team constraints (must reuse an existing framework,
  existing observability stack, team's experience level).

If `$ARGUMENTS` points at an existing `project_brief.md`/
`concept_brief.md`, read it first and only ask what it leaves open.

### Stages 1-8 — run each skill in order, gated

Run these skills strictly in order. Do not start stage N+1 until stage N's
output file is at `Status: APPROVED`:

1. `agent-decision-single-vs-multi` → `system_design/01_agent_topology.md`
2. `agent-decision-design-pattern` → `system_design/02_design_pattern.md`
3. `agent-decision-runtime-deployment-shape` →
   `system_design/03_runtime_deployment_shape.md`
4. `agent-decision-tools-and-authorization` →
   `system_design/04_tools_and_authorization.md` — for every tool this
   stage identifies as external (calls a third-party API/SaaS, not
   in-house logic), it internally invokes
   `agent-decision-external-tool-sourcing` per tool: free options
   researched and recommended first, a real paid option with actual
   pricing presented and approved/declined if no free option covers the
   need, and — if declined — concrete alternative approaches researched
   and presented (e.g. a public site the agent can browse instead of a
   paid data API, with its fidelity/reliability tradeoff stated
   honestly) before falling back to an explicit statement of what
   capability the agent loses, confirmed with the user before
   continuing. This happens inside stage 4's single draft/approval
   cycle, not as a separate gated stage.
5. `agent-decision-memory` → `system_design/05_memory.md`
6. `agent-decision-context-engineering` →
   `system_design/06_context_engineering.md`
7. `agent-decision-loop-engineering` → `system_design/07_loop_engineering.md`
8. `agent-decision-eval-security-guardrails` →
   `system_design/08_eval_security_guardrails.md`

After each stage's skill produces its draft file:
1. Show the draft to the user in full.
2. Ask explicitly: approve as-is, revise this stage, or jump back to an
   earlier stage.
3. **Approve** → mark `Status: APPROVED` in the file, move to the next
   stage.
4. **Revise this stage** → re-run the same skill with the user's
   correction, don't silently patch the file yourself.
5. **Jump back to an earlier stage** → re-run that stage's skill, and once
   it's re-approved, mark every stage *after* it (including any already
   approved) back to `Status: PENDING APPROVAL` and re-run them in order —
   a change to an earlier decision invalidates everything downstream that
   assumed it, even if the user thinks only the earlier stage needs
   revisiting. Say this explicitly when it happens, don't do it silently.

### Stage 9 — Assemble

Once stage 8 is approved, run `agent-system-design-assemble` to produce
the final `architecture_design.md`. This step makes no new decisions —
if it finds a stage file that isn't approved, stop and say which one.

### After assembly

Show the assembled document. Recommend `technical-design` next (or
`write-project-brief`/`write-concept-brief` first if no brief exists yet
at the location `architecture_design.md` was written to), pointing it at
the assembled document's sections as resolved inputs.

## Ground rules

- Never skip a stage or infer its answer from context — each one is a
  distinct decision with its own rubric; skipping defeats the purpose of
  a newcomer-facing, staged design process.
- Never let a later stage silently override an earlier one's decision —
  if a later stage's questions surface a real conflict with an earlier
  stage's answer, stop and send the user back to the earlier stage rather
  than reconciling it unilaterally.
- If the user wants the fast, one-shot version instead of this staged
  walkthrough, tell them to use `agent-architecture-design` directly — do
  not silently compress this command's stages to imitate it.
