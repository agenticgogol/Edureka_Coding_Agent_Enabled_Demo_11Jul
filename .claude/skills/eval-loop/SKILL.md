---
name: eval-loop
description: State machine over the discovery/measurement/ops pipeline (phases 0-8). Inspects evals/ to determine the current phase, reports state, and runs only the next legal step — never a forward skip past an unmet gate.
disable-model-invocation: true
---

# eval-loop

The orchestrator. Do not reference any other skill's `/name` directly in
this file's prose or in what you say to the user beyond what's necessary to
name the next step — resolve which skill covers "phase N" from the table
below at run time, so this file (and your responses) stay correct if the
suite is later packaged as a plugin and every skill's invocation name gets
namespaced.

## The phases

| # | Covers |
|---|---|
| 0 | Bootstrap: entrypoint detection, `evals/` scaffold, `spec.md` |
| 1 | Dataset: dimensions, sampled tuples, generated queries, traces |
| 2 | Open coding: freeform annotation, first-failure-turn marking |
| 3 | Axial coding: taxonomy synthesis, backlog |
| 4 | Evaluator design: code-vs-judge routing, code evals written |
| 5 | Judge authoring: split, then one judge prompt per judge-routed failure mode, with the exact judge model id pinned |
| 6 | Judge alignment: label, calibrate, bias-correct |
| 7 | CI wiring: golden set, test-split lock hook, gated workflow |
| 8 | Cost optimization / improve |

`eval-report-new`, `retrieval-eval-new`, and `trajectory-eval-new` are not
gated phases — they're read-only or side-analyses that can run whenever
their own prerequisites (traces, retrieval/trajectory data) exist,
independent of where the main phase pointer sits. Don't route to them from
this state machine; the user invokes them directly.

## Step 1 — Determine current state

Read [references/phase_detection.md](references/phase_detection.md) and
follow it exactly: read `evals/pipeline_state.json` (create it if absent —
`{"cycle": 1, "last_completed_phase": -1, "history": []}`) and cross-check
against the artifacts each phase produces. Report to the user: current
cycle, current phase, and the phase's completion status (in progress /
ready to start / blocked — see gates below).

## Step 2 — Enforce the hard gates before naming the next step

Three gates exist beyond simple artifact presence. Check these regardless of
what the user asked for — they block the *pipeline's* progression, not just
a specific request:

**Gate A — evaluator-design (phase 4) requires a real taxonomy.**
`evals/taxonomy.yaml` must exist, be non-empty, and every entry must satisfy
`count == len(member_trace_ids)` and `count > 0` (the same invariant
`evallib.schema.AxialCode` enforces at write time — this gate is checking
that the file wasn't hand-edited into an inconsistent state afterward).
**Why:** routing a failure mode to code-vs-judge before the taxonomy is real
means routing decisions for categories that were never actually derived
from data — garbage in, garbage routing.

**Gate B — eval-ci (phase 7) requires every active judge to be validated.**
For every `method: judge` entry in `evals/evaluators/routing.yaml`, there
must be a matching entry in `evals/results/metrics.json` with non-null
`tpr` and `tnr`. **Why:** CI gates a build on these numbers; an unvalidated
judge's pass/fail signal is not known to mean anything, so wiring it into CI
launders an unmeasured judge into an authoritative-looking gate (this is
exactly what hook H4 warns about at write time — this gate is the
pipeline-level enforcement of the same rule).

**Gate C — cost-optimize (phase 8) requires the backlog to have no open
high-severity items.** Read `evals/backlog.md` / `evals/taxonomy.yaml`: any
code with `severity` `high` or `critical` must be closed — for a
`method: code` route, its code eval passes in the current run; for a
`method: judge` route, it has a validated `metrics.json` entry. **Why:**
optimizing cost changes the agent's behavior; doing that while a
high-severity failure is still unaddressed makes it impossible to tell
whether a later regression is the cost change or the pre-existing failure —
see `cost-optimize-new`'s own step 0 for the same gate enforced again at
that skill's entry point (defense in depth, not redundant).

## Step 3 — Run only the next legal step

Once gates are checked: invoke the skill that covers the current phase (by
role/number, resolved at runtime — never hardcode its `/name`). Do not
pre-run a later phase's setup "to save time." Do not run more than one
phase per `eval-loop` invocation — report completion and let the user
decide whether to continue, since each phase (especially 2, 3, 6) involves
interview/approval checkpoints that shouldn't be silently chained.

After the invoked skill completes, update `evals/pipeline_state.json`
(`last_completed_phase`, append to `history`). If the completed phase was 8,
increment `cycle` and set the state so the next `eval-loop` run reports
phase 2 as current — per `references/phase_detection.md`'s cycle-reset
section, not phase 3 onward even though those files still exist from the
prior cycle.

## Step 4 — Forward-skip requests

If the user asks to jump ahead of the current phase (e.g. "just set up CI"
while still in phase 3, or "run cost-optimize" with open high-severity
items): **do not comply, and do not silently redirect to the current phase
either** — name the specific gate that's unmet, in terms of what's actually
missing (not just "gate B failed"), and explain in one or two sentences why
that gate exists (pull the rationale from Step 2 — don't invent a new one).
Then state what the current legal phase is and offer to run that instead.
Never comply with a forward skip just because the user is confident it's
fine — the gates encode why "confident" isn't sufficient here (kappa,
calibration, and severity-closure are exactly the things intuition gets
wrong).

## Step 5 — Report

Every invocation ends with: current cycle/phase, what ran (if anything),
what's now unblocked, and — if a gate blocked the request — which gate and
why. Keep this compact; detailed output belongs to the phase skill that ran,
not to this orchestrator's own report.
