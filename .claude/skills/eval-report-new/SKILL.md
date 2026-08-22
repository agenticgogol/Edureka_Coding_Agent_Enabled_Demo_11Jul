---
name: eval-report-new
description: Assemble evals/scorecard.md — failure taxonomy with counts, per-mode judge TPR/TNR, corrected pass rates with CIs, open backlog, and cost per query. Flags any metric backed by an unvalidated judge. Read-only. Use to check current eval status or produce a summary for stakeholders.
---

# eval-report-new

Assembles a single point-in-time scorecard from whatever eval-suite state
already exists. **Read-only** — this skill never writes to `evals/labels/`,
`evals/traces.jsonl`, `evals/taxonomy.yaml`, or any other pipeline input; it
only reads and writes `evals/scorecard.md`. If asked to fix, relabel, or
re-run anything it finds wanting, say that belongs to the relevant skill
(`judge-align-new`, `axial-coding-new`, etc.) instead of doing it here.

## Step 1 — Gather

Read whatever of the following exist (skip and note as "not yet run" for
anything missing — a partial scorecard is still useful, don't refuse just
because the pipeline is incomplete):

- `evals/taxonomy.yaml` — failure modes, definitions, severities, counts.
- `evals/evaluators/routing.yaml` — which modes are code vs. judge.
- `evals/results/metrics.json` — per-mode `MetricsRecord` (tpr, tnr,
  p_observed, theta_hat, ci_low, ci_high, n_test).
- `evals/backlog.md` — ranked open items.
- `evals/config.yaml` and any cost/token logging the agent already
  produces — for cost per query.
- `evals/results/ci_run_latest.json` if `eval-ci-new` has run — most recent
  CI gate result.

## Step 2 — Flag unvalidated judges

For every failure mode in `routing.yaml` with `method: judge`, check whether
it has a corresponding entry in `evals/results/metrics.json`. **Any judge
without one is unvalidated** — this mirrors hook H4's rule. Never report a
pass rate, TPR/TNR, or theta_hat for an unvalidated judge as if it were
trustworthy; if `evals/judges/<id>.md` exists but has no metrics entry, list
it in the scorecard under a clearly separated "unvalidated — do not cite"
section rather than the main table, even if the judge has been informally
run and produces numbers somewhere.

## Step 3 — Write evals/scorecard.md

```markdown
# Eval Scorecard — <agent name> — <date>

## Failure taxonomy
| Code | Label | Severity | Count | Route |
|---|---|---|---|---|
| skipped-eligibility-check | ... | high | 6 | code |
| tone-mismatch | ... | medium | 4 | judge (validated) |
| ... | ... | ... | ... | judge (**UNVALIDATED**) |

## Validated judge performance
| Failure mode | n_test | TPR | TNR | Observed rate | Corrected rate (theta_hat) | 95% CI | CI width |
|---|---|---|---|---|---|---|---|
| tone-mismatch | 40 | 0.85 | 0.90 | 0.22 | 0.19 | [0.11, 0.28] | 17 pts |

## Unvalidated judges — do not cite these numbers
- <failure_mode_id>: judge exists, no metrics.json entry. Run `/judge-align-new <id>`.

## Open backlog (top items)
<pull directly from evals/backlog.md, don't re-rank>

## Cost
- Cost per query: $<x> (source: <where this came from>)
- <cascade / optimization notes if evals/results has any>

## CI status
<latest gate result if evals/results/ci_run_latest.json exists, else "CI not yet wired — run /eval-ci-new">
```

State CI width in the same plain-language terms `judge-align-new` uses
(e.g. "17 percentage points — wide; more test-split volume would tighten
this") rather than only the raw numbers — a reader who wasn't in the
calibration session needs the same caveat.

## Step 4 — Report

Confirm the file path and summarize in 2-3 sentences: how many failure
modes are fully validated vs. still open/unvalidated, and the single
biggest open risk (highest severity x count item, or the least-tight CI on
a high-severity mode).
