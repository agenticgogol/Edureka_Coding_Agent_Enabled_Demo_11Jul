# Phase detection — how to read evals/ state

`eval-loop` never asks the user what phase they're on — it infers it from
disk. State lives in two places, both under `evals/` and both consulted
together (a mismatch between them is itself worth reporting, not silently
resolved one way):

1. **Artifacts** — the files each phase's skill actually produces.
2. **`evals/pipeline_state.json`** — `{"cycle": <int>, "last_completed_phase": <int>, "history": [{"phase": <int>, "cycle": <int>, "completed_at": "<iso date>"}]}`.
   This exists because artifact presence alone can't distinguish "phase 3
   was never run" from "phase 3 ran in cycle 1 and we're now in cycle 2 and
   deliberately revisiting it" — see the phase-8-loops-to-phase-2 rule.
   `eval-loop` creates this file on first run if absent (cycle 1,
   `last_completed_phase: -1`) and updates it after every phase it runs.

## Phase -> artifact map

| Phase | Skill | Artifact(s) that mark it complete |
|---|---|---|
| 0 | eval-init-new | `evals/spec.md` with >=1 rule, `evals/config.yaml` |
| 1 | eval-dataset-new | `evals/dimensions.yaml`, `evals/traces.jsonl` non-empty |
| 2 | open-codin-new | `evals/open_codes.jsonl` covers every trace_id in `evals/traces.jsonl` (every trace has an OpenCode record) |
| 3 | axial-coding-new | `evals/taxonomy.yaml` non-empty, every entry has `count == len(member_trace_ids)` and `count > 0` |
| 4 | evaluator-design-new | `evals/evaluators/routing.yaml` has one entry per `taxonomy.yaml` code |
| 5 | judge-split-new, judge-builder-new | every `method: judge` entry in `routing.yaml` has both `evals/labels/<id>_splits.json` (judge-split-new; run this one first — see its own SKILL.md for why it exists as a separate step) and `evals/judges/<id>.md` with a `judge_model_id` frontmatter field (judge-builder-new) |
| 6 | judge-align-new | every judge from phase 5 has a `MetricsRecord` in `evals/results/metrics.json` with non-null `tpr`/`tnr`, computed under the model id pinned in that judge's frontmatter |
| 7 | eval-ci-new | `.github/workflows/eval_gate.yml` exists, `evals/golden/golden_set.jsonl` non-empty |
| 8 | cost-optimize-new | ran at least once this cycle (tracked in `pipeline_state.json` history, since this phase doesn't gate on a single artifact the way others do) |

## Determining "current phase" (the next legal step)

Walk the table top to bottom. The current phase is the **first** one whose
artifact condition is not yet met. If all are met through phase 7 and
phase 8 hasn't run this cycle, phase 8 is next (subject to its own gate —
see SKILL.md). If phase 8 *has* run this cycle, the next phase is **2**, in
a new cycle (see below) — never phase 3 or later, even though `taxonomy.yaml`
etc. from the prior cycle still exist on disk; that's exactly what
`pipeline_state.json` overrides.

## Starting a new cycle after phase 8

When phase 8 completes: increment `cycle`, set `last_completed_phase` to
mark that phase 8 finished the *previous* cycle, and report to the user that
`evals/traces.jsonl`, `open_codes.jsonl`, and `taxonomy.yaml` are now stale
relative to the improved agent — the failure distribution shifts after every
fix, so re-deriving from fresh traces is not optional busywork. Do not
delete or archive the prior cycle's files yourself; tell the user
`open-codin-new` (phase 2) needs fresh traces first, which likely means
re-running `eval-dataset-new`-generated queries against the now-changed
agent to get new traces before open coding can proceed — flag this as the
practical first sub-step even though the gate table names phase 2, not
phase 1, as "next."

## Drift between artifacts and pipeline_state.json

If `pipeline_state.json` says a phase completed but its artifact is now
missing or empty (e.g. someone deleted `evals/taxonomy.yaml`), or vice
versa, report the mismatch to the user before proceeding — don't silently
trust one source over the other.
