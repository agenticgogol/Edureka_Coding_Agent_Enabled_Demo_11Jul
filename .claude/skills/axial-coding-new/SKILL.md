---
name: axial-coding-new
description: Delegate bulk trace/note reading to the trace-reader subagent, cluster open codes into a candidate taxonomy, get user approval, and write taxonomy.yaml + a frequency x severity x fixability backlog.md.
disable-model-invocation: true
---

# axial-coding-new

Phase 3 of the discovery pipeline: axial coding. Requires
`evals/open_codes.jsonl` from `/open-codin-new` — if missing or empty, stop
and say so.

**Categories are derived from the data, not imposed on it.** If the user
tries to hand you a list of failure categories up front ("just use:
hallucination, tool error, refusal, tone"), push back before doing anything
else: explain that axial coding's entire value is discovering the categories
that are actually present in *this* agent's failures, in the annotator's own
language — a pre-supplied list either misses categories nobody thought of yet
or forces real failures into an ill-fitting bucket. Offer instead: run the
clustering pass first, then compare the emergent taxonomy against their list
and reconcile differences together. If they insist, comply but note in
`taxonomy.yaml`'s notes that categories were user-supplied rather than
derived, so nobody later mistakes it for a grounded-theory taxonomy.

## Step 1 — Delegate bulk reading to trace-reader

Don't read all of `evals/open_codes.jsonl` and the full traces it references
into your own context — that's exactly what the `trace-reader` subagent
exists to avoid (its job is batching/summarizing large collections down to
what a clustering pass actually needs, at bounded turn cost; see its own
agent file for how it batches).

Invoke `trace-reader` (Agent tool, `subagent_type: trace-reader`) with: the
paths to `evals/open_codes.jsonl` and `evals/traces.jsonl`, and the ask —
return every open code's `note`, `is_failure`, `first_failure_turn_index`,
`trace_id`, plus enough trace context per failure (the turn at
`first_failure_turn_index` and the final response) to judge what went wrong,
grouped in a form ready for clustering rather than as raw file dumps. Ask it
to also surface, per note, whether it carries an `open-codin-new` hint-mode
provenance prefix (`[hint-confirmed]` / `[hint-edited]` / `[independent]` —
absent entirely means hint mode was off for that note).

**Provenance affects how much you trust a note's wording, not whether you
use it.** A `[hint-confirmed]` note's phrasing came partly from an AI guess,
not purely from the annotator — weight `[independent]` and `[hint-edited]`
notes more heavily when a cluster's boundary is ambiguous, and if a cluster
is made up mostly of `[hint-confirmed]` notes with very similar wording,
flag that to the user before finalizing it: near-identical AI-generated
phrasing can look like a strong cluster signal while actually reflecting the
hint generator's own vocabulary repeating across traces, not a real pattern
in the agent's behavior.

## Step 2 — Cluster into candidate axial codes

From what `trace-reader` returns, group the failure notes into candidate
clusters by what actually went wrong — read the notes' own language rather
than reaching for a stock taxonomy. A cluster needs at least 2 member traces;
a single-trace oddity stays uncategorized for this pass rather than becoming
a category of one (note it to the user as a "singleton, watch for repeats").

For each cluster, draft:

- `label` — short, specific, in the annotators' vocabulary where possible.
- `definition` — one or two sentences, specific enough that a new trace could
  be checked against it unambiguously (this definition becomes the seed for
  a judge prompt later — vague definitions produce unreliable judges).
- `member_trace_ids` — every trace_id in the cluster.
- `count` — `len(member_trace_ids)`.
- `severity` (`low`/`medium`/`high`/`critical`) — your assessment of user
  impact if this failure mode reaches production; use `evals/spec.md`'s
  must-always/must-never rules to calibrate (a `must-never` violation is
  never `low`).

## Step 3 — Get approval

Show the full proposed taxonomy — every cluster's label, definition, count,
severity, and 1-2 example notes per cluster — before writing anything.
Explicitly ask the user to approve, merge, split, rename, or reject each
cluster. Do not write `taxonomy.yaml` until they've responded; if they
request changes, apply them and show the result again before writing.

## Step 4 — Write taxonomy.yaml

One `evallib.schema.AxialCode` per approved cluster (`code_id` = a stable
slug derived from the label, e.g. `skipped-eligibility-check`). Validate each
before writing — `AxialCode` rejects a `count` that doesn't match
`len(member_trace_ids)`, which is exactly the kind of copy-paste error a
manual edit here would introduce. Dump the list to `evals/taxonomy.yaml` as
YAML (`model_dump()` per code, `severity` as its plain string value).

## Step 5 — Write backlog.md

Rank every code by `frequency × severity_weight × fixability`:

- `frequency` = `count`.
- `severity_weight`: `low=1, medium=2, high=3, critical=4`.
- `fixability` (1-5, your estimate, state your reasoning per code): how
  tractable a fix looks given the failure's nature — e.g. "add a tool call
  before responding" is more fixable than "underlying model reasoning gap."
  Ask the user to sanity-check fixability scores that materially change the
  ranking before finalizing.

Write `evals/backlog.md`:

```markdown
# Failure backlog — ranked by frequency x severity x fixability

| Rank | Code | Count | Severity | Fixability | Score | Notes |
|---|---|---|---|---|---|---|
| 1 | skipped-eligibility-check | 6 | high | 4 | 72 | ... |
```

Include one line per code explaining the fixability call, since that number
is a judgment nothing else in this pipeline validates.

## Step 6 — Report

Report code count, total traces covered vs. total failure traces, and the
top 3 backlog items. Tell the user the next phase (labeling a train/dev/test
split and building judges) is not part of this skill.
