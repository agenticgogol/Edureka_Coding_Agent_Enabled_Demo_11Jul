---
name: agent-system-design-assemble
description: Final stage of the staged agent-system-design pipeline. Stitches the eight approved stage files into one architecture_design.md. Makes no new decisions — pure assembly, used after all eight decision stages are approved.
---

# Agent System Design: Assemble

The last step of `/agent-system-design`. Reads the eight approved stage
files under `system_design/` and stitches them into a single
`architecture_design.md`, matching the same output schema
`agent-architecture-design` produces for its one-shot path — so downstream
skills (`technical-design`, `write-project-brief`) can consume either
path's output identically.

This skill makes **no new decisions**. If any of the eight stage files is
missing or not at `Status: APPROVED`, stop and say which one, rather than
filling the gap with a guess.

## When to use

- Called by `/agent-system-design` as its final step, after stage 8 is
  approved.
- Never invoked standalone against an incomplete set of stage files.

## Input

- `system_design/01_agent_topology.md` through
  `system_design/08_eval_security_guardrails.md`, all `Status: APPROVED`.

## Procedure

### 1. Verify completeness

Check all eight files exist and are approved. List any that are missing
or still pending, and stop if so.

### 2. Map stage files onto the unified schema

```markdown
# Architecture Design: <Name>

## Business outcome
<from stage 1's restated business problem>

## Decision walkthrough
<condensed cross-reference of all eight stages' Q&A, in order — link to
the individual stage files rather than repeating every line, so the
document stays readable>

## Chosen architecture pattern
<stage 1's topology + stage 2's pattern + ASCII diagram from stage 2>

## Rejected alternatives
<stage 1 and stage 2's rejected alternatives>

## Runtime & deployment shape
<stage 3, verbatim>

## Tool & side-effect boundaries
<stage 4's tool table, verbatim>

## Knowledge & state design
<stage 5's per-category table, verbatim>

## Context engineering
<stage 6, verbatim>

## Loop engineering
<stage 7, verbatim>

## Non-functional budgets & overlays
<stage 8's cost/latency check + security + guardrails>

## Evaluation & observability
<stage 8's eval + observability sub-rubrics>

## Architecture-change triggers
<synthesize from all stages: what future signal — volume growth beyond
stage 3's ceiling, a new tool with a higher auth tier, a repeated
step-ceiling breach from stage 7 — would justify revisiting which
specific stage>
```

### 3. Write `system_design/architecture_design.md` (or
`projects/<slug>/architecture_design.md` /
`concepts/<slug>/architecture_design.md` if a brief already exists at that
location)

### 4. Show the assembled document and recommend next steps

Recommend `technical-design` next (or `write-project-brief`/
`write-concept-brief` first, if no brief exists yet), pointing it at this
document's sections as resolved inputs — same handoff contract as
`agent-architecture-design`.

## Ground rules

- Never invent content for a section — every line here should trace back
  to one of the eight stage files; if a section would be empty, say so
  explicitly rather than padding it.
- Never assemble from an unapproved stage file.
- Preserve each stage's stated rejected-alternatives and rationale rather
  than compressing them into a bare conclusion — the audit trail is the
  point of the staged process.
