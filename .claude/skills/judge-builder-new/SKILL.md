---
name: judge-builder-new
description: Write (author) one LLM judge prompt per failure mode routed to "judge" in evals/evaluators/routing.yaml, using assets/judge_template.md. Enforces binary output, critique-before-label, train-only few-shot, and spec.md-grounded definitions. Use after evaluator-design-new routes a failure mode to judge, or when asked to "write a judge" or "build a judge prompt" for a specific failure mode.
---

# judge-builder-new

Phase 5: judge authoring. Requires `evals/evaluators/routing.yaml` from
`/evaluator-design-new` — if missing, say so and stop. Operates one failure
mode at a time; ask which `failure_mode_id` (from the `method: judge`
entries) if not specified.

## Non-negotiables — enforce all five, every time

1. **Binary PASS/FAIL output only.** Never a 1-5 scale, a percentage, or a
   confidence score. A judge that outputs anything but PASS/FAIL cannot be
   calibrated by `judge-align-new`'s TPR/TNR machinery, which is defined
   over binary confusion matrices.
2. **Critique before label.** The template's ordering (critique text, then
   the `LABEL:` line) is load-bearing, not stylistic — see the template's
   own header comment for why. Never reorder it, never let the user talk you
   into "just output the label, skip the reasoning" for speed.
3. **Few-shot examples come ONLY from the train split.** Never dev, never
   test — those exist solely for calibration in `judge-align-new`, and a
   dev/test trace leaking into the prompt as a few-shot example
   contaminates that calibration (the judge would then be "tested" on data
   it already saw). Read `evals/labels/<failure_mode_id>_splits.json`
   (written by `judge-split-new`) to know which trace_ids are `train`. **If
   no split-assignment file exists yet, stop and tell the user to run
   `/judge-split-new <failure_mode_id>` first** — do not guess which traces
   are safe to use as few-shot examples.
4. **The definition is grounded in `evals/spec.md`, not generic quality
   language.** Every judge must cite a specific rule ID from `spec.md` (and
   the `taxonomy.yaml` definition) in its "What you are checking" section.
5. **The exact judge model id is pinned in the prompt's frontmatter before
   any few-shot curation happens — never a floating alias, never left for a
   later skill to ask about separately.** See Step 0. A judge calibrated
   against one model id (or an alias like `gpt-4o` that can silently
   resolve to a different snapshot over time) and then run in CI/production
   under a different one is not actually validated — `judge-align-new`'s
   TPR/TNR and `eval-ci-new`'s regression gate both describe the pinned
   model's behavior specifically, not "whatever this judge happens to run
   as."

## Refuse generic "helpfulness" / "quality" judges

If the user asks for a judge on something like "helpfulness," "quality," or
"good response" without it mapping to a specific failure mode in
`taxonomy.yaml`, decline and ask which failure mode it actually corresponds
to. If none does, tell them this belongs in `/eval-init-new` (a new
must-always/must-never rule) or `/axial-coding-new` (a new taxonomy code)
first — not as an ad hoc judge with no grounded definition, since an
ungrounded judge can't be calibrated against anything meaningful.

## Step 0 — Confirm the split exists, then pin the exact judge model

Check for `evals/labels/<failure_mode_id>_splits.json`. If it doesn't exist,
stop here and tell the user to run `/judge-split-new <failure_mode_id>`
first — do not create it yourself or guess at train/dev/test membership.

Then ask the user directly, before doing anything else:

> "What exact, dated model id should this judge run as — everywhere,
> permanently? This gets written into the judge prompt itself, and every
> later step (dev/test calibration in `judge-align-new`, the CI gate in
> `eval-ci-new`) reads it from there rather than picking one independently.
> Use a real dated snapshot (e.g. `gpt-4o-2024-08-06`), not a floating alias
> like `gpt-4o` or `latest` — an alias can resolve to a different
> underlying model over time, which would silently invalidate this judge's
> calibration without anyone changing a single file. If you calibrate
> against one model and then run in CI under a different one, the CI gate
> is not actually measuring what was validated — this is the single most
> expensive mistake to make in this pipeline, because fixing it later means
> redoing all of dev+test+population calibration from scratch."

Record the answer — it goes into the judge prompt's frontmatter in Step 3,
and nothing past this point should reference a model id that didn't come
from this answer.

## Step 1 — Gather inputs

Read, for the target `failure_mode_id`: its entry in `evals/taxonomy.yaml`
(definition, severity), the relevant rule(s) in `evals/spec.md`, and the
train-split trace_ids from the split-assignment file written by
`judge-split-new`. Pull the full `Trace` records for those train trace_ids
from `evals/traces.jsonl`.

## Step 2 — Curate few-shot examples with the user

Show the user 4-8 candidate train-split traces relevant to this failure mode
(prioritize any that were in this code's `member_trace_ids` in
`taxonomy.yaml`, plus a few that look like plausible near-misses). Ask them
to pick 3-6 and confirm each one's PASS/FAIL label and a short reasoning —
this is a lightweight curation pass for the prompt, distinct from the formal
dev/test annotation loop in `judge-align-new`. Look specifically for one
near-miss pair (a PASS trace that superficially resembles a FAIL one) — call
this out to the user if you don't see one in the candidates, since it's the
single highest-value example type for narrowing the judge's boundary.

## Step 3 — Fill the template

Copy `assets/judge_template.md` to `evals/judges/<failure_mode_id>.md` and
fill every placeholder: the `judge_model_id` frontmatter field (Step 0's
answer — a real dated snapshot, never an alias), the definition (spec.md
rule + taxonomy.yaml definition), what's explicitly out of scope, and the
curated few-shot examples with critiques and labels.

## Step 4 — Self-check before handing off

Re-read the filled prompt and confirm: the frontmatter's `judge_model_id`
is present and looks like a real dated snapshot (not `gpt-4o`, not
`latest`, not still the template placeholder), output instruction says
PASS/FAIL only (no scale language anywhere), critique appears before the
label line, every few-shot example's trace_id is confirmed train-split, and
the definition section quotes a real `spec.md` rule ID. Fix anything that
doesn't hold — don't hand off a judge prompt that fails its own non-
negotiables.

## Step 5 — Report

Report the failure_mode_id, the pinned `judge_model_id`, the spec.md
rule(s) it's grounded in, few-shot count (PASS/FAIL split), and confirm the
near-miss pair status. Tell the user the next step is `/judge-align-new
<failure_mode_id>` for calibration — this judge is unvalidated until that
runs, and every call `judge-align-new` makes will use the pinned model id
automatically (see its own SKILL.md), not a separately-chosen one.
