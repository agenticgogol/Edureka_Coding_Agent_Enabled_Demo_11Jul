---
name: eval-ci-new
description: Promote labeled traces into evals/golden/, generate a GitHub Actions eval-gate workflow (pinned model, code evals + validated judges, regression threshold), and install the test-split-locking hook.
disable-model-invocation: true
---

# eval-ci-new

Phase 7: CI wiring. Requires at least one entry in `evals/results/metrics.json`
(a validated judge) or `evals/evaluators/routing.yaml` with `method: code`
entries — if neither exists, tell the user there's nothing to gate on yet
and stop.

## Step 1 — Promote labeled traces into evals/golden/

Read every `evals/labels/*.jsonl` (`LabelRecord` rows) and consolidate:

1. Every row with `split == "test"`, across all failure modes, into a single
   canonical `evals/labels/test.jsonl` — this is the physical file hook H1
   protects, so it must exist as one file regardless of how many
   per-failure-mode label files fed it. If a trace_id/failure_mode_id pair
   already has a row there, don't duplicate it.
2. For every `Trace` referenced by a promoted `LabelRecord`, copy the full
   trace into `evals/golden/golden_set.jsonl` (dedup by `query_id`) —
   golden set = the traces CI will actually re-run evaluators/judges
   against, paired with their trusted human labels.

Validate both outputs with `python -m evallib.cli validate`.

## Step 2 — Install the test-split lock hook (H1)

Copy `assets/lock_test_split.py` to `.claude/hooks/lock_test_split.py`
verbatim — read its own header comment for what it does and why it
pattern-matches on filename rather than parsing file contents.

Merge into `.claude/settings.json` (create if absent, merge if present —
never overwrite unrelated existing hooks):

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Read|Edit|Write|Bash|Grep|Glob",
        "hooks": [
          {
            "type": "command",
            "command": "python3 ${CLAUDE_PROJECT_DIR}/.claude/hooks/lock_test_split.py"
          }
        ]
      }
    ]
  }
}
```

If a `PreToolUse` entry already exists for one or more of these tools, add
this hook to its `hooks` array rather than replacing the entry — multiple
hooks on the same matcher all run. After writing, tell the user to run
`/hooks` to confirm it registered.

## Step 3 — Generate the CI scripts

The workflow (Step 4) calls two scripts that don't exist yet — write them to
`evals/scripts/`, adapted to this project's actual judge-invocation code
(reuse whatever `judge-align-new`'s dev/test runs already call — don't
invent a second judge-calling path):

- **`run_judge_ci.py`** — for every `failure_mode_id` in
  `evals/evaluators/routing.yaml` with `method: judge`: look it up in
  `evals/results/metrics.json`; if absent, print a warning (mirroring hook
  H4's rule — an unvalidated judge is not safe to gate on) and skip it;
  otherwise run that judge — under the exact `judge_model_id` pinned in its
  own `evals/judges/<failure_mode_id>.md` frontmatter, never a single
  global model env var shared across every judge — over
  `evals/golden/golden_set.jsonl` and write per-trace results plus the
  aggregate pass rate to `evals/results/ci_run_latest.json`. Also run every
  `method: code` evaluator from `evals/evaluators/*.py` over the same
  golden set the same way, merged into the same output file.
- **`check_regression.py`** — loads `evals/results/ci_run_latest.json` (this
  run) and `evals/results/metrics.json` (baseline `theta_hat` per failure
  mode), computes the drop per failure mode, and exits non-zero if any drop
  exceeds `--threshold`. Print a clear per-failure-mode table either way
  (pass or fail) so a green CI run still shows the numbers, not just "OK."
  For every failure mode it reports on, also call
  `evals/scripts/append_metrics_history.py --run-type ci ...` (see
  `eval-dashboard-new`'s SKILL.md for the exact flags and status-string
  mapping) so this CI run joins `evals/results/dashboard.html`'s history —
  if that script doesn't exist yet in this project, run `/eval-dashboard-new`
  once to set it up before wiring this call in.

## Step 4 — Generate the workflow

Copy `assets/eval_gate.yml` to `.github/workflows/eval_gate.yml`.

**Do not ask the user to pick a judge model id here.** Every `method: judge`
entry in `routing.yaml` already has a pinned, exact model id in its
`evals/judges/<failure_mode_id>.md` frontmatter (`judge_model_id`, written
by `judge-builder-new`, the exact model `judge-align-new` calibrated
against) — read it from there and use it directly in the workflow/scripts.
Asking a second time here and getting a different answer is precisely how a
CI gate ends up running a judge under a model different from the one its
`metrics.json` baseline was calibrated against, silently invalidating the
whole gate. If a judge-routed failure mode has no `evals/judges/<id>.md` at
all yet (nothing to read a model id from), that's Step 1's "nothing to gate
on" case for that mode specifically — skip it in the generated scripts with
the same warning pattern as an uncalibrated judge, don't invent a model id
for it.

If more than one judge-routed failure mode exists with **different** pinned
model ids, the generated `run_judge_ci.py` must call each judge under its
own pinned id (a small per-failure-mode lookup, not a single global env
var) — say this explicitly to the user if it comes up, since it means the
workflow's env block can't rely on one `EVAL_MODEL_ID` for every judge.

Set `EVAL_REGRESSION_THRESHOLD` from the user (default 0.05 = 5 percentage
points on corrected pass rate) — ask if they want a different tolerance,
and if any failure mode is `critical` severity in `taxonomy.yaml`, suggest a
tighter threshold for it specifically (the generated workflow can pass a
per-mode threshold map to `check_regression.py` if the user wants that
granularity — ask before adding that complexity, don't add it unprompted).

Add the agent's actual source paths to the workflow's `paths:` trigger list
(the template leaves a placeholder comment) so a code change to the agent,
not just an `evals/` change, re-runs the gate.

## Step 5 — Report

Report: golden set size, test.jsonl row count, hook installed (yes/no +
path), workflow written (yes/no + path), the model id(s) pinned per
judge-routed failure mode (read from frontmatter, not chosen in this
skill), and regression threshold. Tell the user to open a throwaway PR to
confirm the workflow actually runs before relying on it.
