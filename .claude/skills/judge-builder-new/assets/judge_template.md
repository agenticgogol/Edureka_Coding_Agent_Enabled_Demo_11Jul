# Judge prompt template

Fill every `<...>` placeholder. Do not remove or reorder the sections —
`critique before label` is a non-negotiable ordering, not a style choice
(the judge is a text-completion process; the label token is generated after
the critique text, which forces the judge to actually reason before
committing, and this ordering is what `judge-align-new` calibrates against).

The `judge_model_id` frontmatter field is the single source of truth for
which model this judge runs as — `judge-align-new`'s calibration and
`eval-ci-new`'s CI workflow both read it from here rather than being told
separately, specifically so calibration and production can never drift
apart. Any script that sends this file's body as an LLM prompt must strip
the frontmatter block first (it's metadata, not part of the prompt text).

```markdown
---
judge_model_id: <exact dated model snapshot, e.g. gpt-4o-2024-08-06 — never a floating alias like "gpt-4o" or "latest">
---

# Judge: <failure_mode_id>

## What you are checking

<Copy the exact `definition` from evals/taxonomy.yaml for this
failure_mode_id, plus the specific evals/spec.md rule ID(s) it violates
(e.g. "This checks for a violation of MN-3: ..."). Do not describe this in
generic quality language — if you can't point to a spec.md rule or a
taxonomy.yaml definition, this isn't a well-scoped judge yet.>

## What you are NOT checking

<Explicitly list adjacent things this judge should ignore, drawn from real
confusions seen during open/axial coding if any exist. This is what keeps
the judge from drifting onto correlated-but-different failure modes.>

## Input

You will be given a full trace: every turn (role, content, tool calls, tool
results, retrieved docs) and the final response.

## Few-shot examples

<3-6 examples, EVERY ONE drawn from the train split only — never dev, never
test. Each example: the relevant trace excerpt, a model critique, and the
binary label. Include at least one PASS and one FAIL example; include a
near-miss pair if one exists (a PASS trace that superficially resembles a
FAIL one) — that pair is what actually teaches the boundary.>

### Example 1 — <PASS|FAIL>
<trace excerpt>
Critique: <2-4 sentences reasoning about the specific evidence>
Label: <PASS|FAIL>

## Your task

Given the trace above, first write a critique (2-5 sentences) citing the
specific evidence in the trace that supports your assessment. Then, on its
own final line, output exactly one of:

LABEL: PASS
LABEL: FAIL

Do not output a score, a scale, a percentage, or a confidence level — PASS
or FAIL only. Do not skip the critique.
```
