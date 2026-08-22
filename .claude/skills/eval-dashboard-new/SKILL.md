---
name: eval-dashboard-new
description: Regenerate evals/results/dashboard.html — a self-contained, offline HTML dashboard tracking every judge-calibration run and every CI gate run's full metric values over time, per failure mode. Not a gated pipeline phase; runs whenever evals/ exists, invoked automatically by judge-align-new and eval-ci-new, or directly by the user any time.
disable-model-invocation: true
---

# eval-dashboard-new

A cross-cutting side skill, like `eval-report-new` — it doesn't gate or get
gated by the phase pipeline. It has two jobs: keep an **append-only history
log** of every metric-producing run, and **regenerate a static HTML
dashboard** from that log.

## Why a separate history log exists

`evals/results/metrics.json` (from `judge-align-new`) and
`evals/results/ci_run_latest.json` (from `eval-ci-new`) are both
**current-value-only** files — each write replaces what was there. Neither
can answer "how has this judge's theta_hat changed across recalibrations"
or "has this failure mode's CI pass rate been trending down." This skill
adds `evals/results/metrics_history.jsonl` as the accumulating record
behind both files, using `evallib.schema.MetricsHistoryRecord` (already
defined in `evallib/schema.py` — check it exists; if the project's
`evallib/` copy predates this, add the class following its canonical
definition, don't invent a parallel shape) and `evallib.jsonl.append_jsonl`
(never `write_jsonl`, which would overwrite prior rows).

## Step 1 — First-time setup for a project

Check whether `evals/scripts/append_metrics_history.py` and
`evals/scripts/render_dashboard.py` already exist. If not, copy both from
this skill's `assets/` directory verbatim — they're project-agnostic (they
only depend on `evallib.schema.MetricsHistoryRecord`, not on anything
specific to one agent). Do not rewrite their logic per project; if a
project genuinely needs a different chart or column, that's a real
extension to make once here and re-copy, not a per-project fork.

## Step 2 — Wire the two producer skills to call the append script

This only needs doing once per project, and should already be true for any
project built after this skill existed — verify it, don't assume:

- **`judge-align-new` step (d)**, right after writing `MetricsRecord` to
  `evals/results/metrics.json`, should also call:
  ```
  python evals/scripts/append_metrics_history.py --run-type calibration \
      --failure-mode-id <id> --method judge --tpr <tpr> --tnr <tnr> \
      --p-observed <p_observed> --theta-hat <theta_hat> --ci-low <ci_low> \
      --ci-high <ci_high> --n-test <n_test> --judge-model-id <pinned model id>
  ```
- **`eval-ci-new`'s `check_regression.py`**, for every failure mode it
  prints a row for (code or judge, "ok"/"REGRESSED"/"no baseline yet"/
  "SKIPPED"), should also call:
  ```
  python evals/scripts/append_metrics_history.py --run-type ci \
      --failure-mode-id <id> --method <code|judge> --ci-rate <current_rate> \
      --baseline-rate <baseline_rate or omit> --regression-status <ok|regressed|no_baseline|skipped_uncalibrated> \
      --n-golden <n>
  ```
  Map `check_regression.py`'s printed status strings to the schema's
  `regression_status` values exactly: "ok" -> `ok`, "REGRESSED" -> `regressed`,
  "no baseline yet" -> `no_baseline`, "SKIPPED (uncalibrated judge)" ->
  `skipped_uncalibrated`.

If either producer script doesn't yet call this, add the call now (a
one-line addition per script, not a rewrite) — this is what makes "auto-
append + auto-regenerate" actually true rather than aspirational.

## Step 3 — Backfill history for any already-completed runs

If `evals/results/metrics.json` already has entries and/or
`evals/results/ci_run_latest.json` already exists, but
`evals/results/metrics_history.jsonl` doesn't yet reflect them, backfill
one history row per existing record now (best-effort timestamps — note in
`--notes` that the row is a backfill of a pre-existing run, e.g. "backfilled
from metrics.json, original run time unknown"). This is a one-time catch-up
so the dashboard isn't empty for work that already happened.

## Step 4 — Regenerate the dashboard

Run `python evals/scripts/render_dashboard.py`. It reads the full
`metrics_history.jsonl`, groups by `failure_mode_id`, and writes
`evals/results/dashboard.html` — for each failure mode: a `theta_hat`
line-with-CI-band chart and a TPR/TNR chart (calibration rows), a
measured-rate-vs-baseline chart with status-colored points (CI rows), and
**a complete data table listing every field of every run**, newest first —
this table is the actual "stores all details of metric values for every
run" requirement; the charts are a summary layer on top of it, not a
replacement for it. Charts and color choices come from the `dataviz`
skill's validated reference palette (already applied in the shipped
script) — if you modify `render_dashboard.py`'s colors, re-run that
skill's validator against your changes.

**Every metric must be explained, not just plotted.** The shipped script
includes a collapsible glossary (every column defined in plain language),
a hover tooltip on every table header, a plain-language "latest" summary
per failure mode (e.g. "true failure rate ≈ 0.15, judge catches 1.00 of
real failures"), and a short caption under every chart explaining what it
shows and how to read it (e.g. the TPR/TNR chart explicitly says this
measures the *judge's* accuracy, not the agent's). If you extend this
script with a new column or chart, add its explanation to
`COLUMN_GLOSSARY` and a matching `chart-note` paragraph in the same pass —
a dashboard field with no explanation defeats the purpose of a dashboard
meant to be read by someone who wasn't in the room when it was built.

Confirm the file was written and briefly describe what's in it (failure
mode count, run count, date range) — don't just say "done."

## Step 5 — Report

Report: whether this was first-time setup or a regeneration, current row
count in `metrics_history.jsonl`, per-failure-mode run counts, and the path
to `evals/results/dashboard.html` (tell the user to open it directly in a
browser — no server needed). If Step 2 found either producer script not
yet wired to append, say so explicitly and confirm you fixed it.
