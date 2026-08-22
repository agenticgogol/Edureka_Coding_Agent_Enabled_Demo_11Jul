---
name: judge-split-new
description: Draw the train/dev/test split for one judge-routed failure mode, before either judge-builder-new (needs train for few-shot curation) or judge-align-new (needs dev/test for labeling+calibration) can run. Breaks the circular dependency between those two skills — always run this one first.
disable-model-invocation: true
argument-hint: "[failure-mode-id]"
---

# judge-split-new

Phase 5a: split assignment. Requires `evals/evaluators/routing.yaml` with a
`method: judge` entry for the target `failure_mode_id` (from
`evaluator-design-new`) — if missing, say so and stop. `$ARGUMENTS` is the
`failure_mode_id`; ask if not given.

**Why this is its own skill, not folded into `judge-builder-new` or
`judge-align-new`:** those two skills used to have a circular dependency —
`judge-builder-new` needs to know which traces are `train`-split before it
can pick few-shot examples, but `judge-align-new` (which used to own split
creation) needs a judge prompt to exist before it can do anything past
labeling. That forced every first-time run to bounce between the two
skills, discovering the missing piece only when the other one blocked.
Splitting is mechanical and has no dependency on a judge prompt existing —
pulling it out into its own skill means both downstream skills can declare
a single, non-circular prerequisite: this one.

If `evals/labels/<failure_mode_id>_splits.json` already exists, read it back
to the user and ask whether to reuse it or redraw (redrawing requires
re-running `judge-builder-new`'s few-shot curation and `judge-align-new`'s
labeling/calibration from scratch, since a new split reassigns which traces
are train vs. dev vs. test — say this explicitly before redrawing).

## Step 1 — Choose the stratification key

The default call is:

```
evallib.stats.stratified_split(traces, by=lambda t: t.dimension_tuple,
                                ratios=(0.2, 0.4, 0.4), random_state=<fixed seed, record it>)
```

**Before running it, check whether `dimension_tuple` actually has repeated
values across the dataset.** `stratified_split` treats every distinct
`by(record)` result as its own stratum and allocates train/dev/test
proportionally *within* each stratum — if every trace's `dimension_tuple` is
unique (common in a small self-driven dataset sampled from a large
cross-product, e.g. 20 traces from a 50+-tuple space), every stratum has
exactly one member, so `round(1 * 0.2)` and `round(1 * 0.4)` both floor to
zero and **100% of traces land in test, with train and dev empty.** This
silently breaks both downstream skills (no train traces for few-shot
examples, no dev traces to iterate against) without raising an error.

Check this before committing to a key:
```python
from collections import Counter
dupe_check = Counter(t.dimension_tuple for t in traces)
```
If every count is 1 (or nearly every one), do not stratify by the full
`dimension_tuple`. Use a coarser key instead — in order of preference:
1. **Whether the trace is a member of this failure mode** (`t.query_id in
   member_trace_ids` from `taxonomy.yaml`) — this is usually the right
   choice specifically for a judge's split, since it guarantees the
   (often rare) positive class is represented in every split rather than
   risking a dev or test split with zero positives, which makes
   `tpr_tnr` raise outright.
2. A single dimension with real repeats (e.g. `t.dimension_tuple[i]` for
   whichever axis has the fewest distinct values — check with the same
   `Counter` pattern).

State which key you used and why in the splits file (see Step 2) — this is
a judgment call worth being able to audit later, not a silent substitution.

## Step 2 — Split and write

Run `stratified_split` with the chosen key, a fixed `random_state` (pick one
and record it — a split must be reproducible, not re-rolled per run), and
ratios `(0.2, 0.4, 0.4)` unless the user asks for different ones.

Write `evals/labels/<failure_mode_id>_splits.json`:

```json
{
  "failure_mode_id": "<failure_mode_id>",
  "random_state": <seed>,
  "strat_key": "<human-readable description of the by= function used, and why, per Step 1>",
  "train": ["<query_id>", ...],
  "dev": ["<query_id>", ...],
  "test": ["<query_id>", ...]
}
```

## Step 3 — Sanity-check the split

Before reporting, confirm:
- `train` is non-empty (judge-builder-new needs at least a few examples).
- `dev` is non-empty (judge-align-new's iteration loop needs traces to run
  against).
- `test` is non-empty (judge-align-new's final validation needs traces).
- If this failure mode has known `member_trace_ids` in `taxonomy.yaml`,
  check whether at least one landed in each of train/dev/test — if not
  (e.g. all positives landed in test), say so plainly: `tpr_tnr` will raise
  a `ValueError` in whichever split has zero positives, and the user should
  decide whether to redraw with a different `random_state` or accept a
  split where, say, TPR simply can't be computed on dev only.

## Step 4 — Report

Report: the failure_mode_id, the stratification key chosen and why, split
sizes (train/dev/test), the seed, and whether every split contains at least
one member trace (if `taxonomy.yaml` has member_trace_ids for this mode).
Tell the user the next step is `/judge-builder-new <failure_mode_id>`.
