---
name: cicd-integrator
description: MUST USE when the user wants the eval wired into CI/CD — "eval gate", "block PRs on eval regressions", "CI for the eval", "GitHub Actions eval", ".github/workflows/eval-gate.yml". Run after baseline-runner and ideally after judge-calibrator so the gate knows whether judges are trustworthy. Trigger eagerly on any mention of automating eval runs on PRs or blocking merges on eval score drops.
---

# CI/CD Integrator

Produces `.github/workflows/eval-gate.yml`, `eval/scripts/compare_to_baseline.py`, and `eval/scripts/post_pr_comment.py`.

## Steps

1. **Read `eval/results/baseline.json`** for the current baseline shape, and `eval/calibration_report.md` if it exists to check judge trust status.

2. **Write `eval/scripts/compare_to_baseline.py`**: runs the eval (reusing baseline-runner's generated `eval/promptfooconfig.yaml`), then compares new results to the stored baseline. Fails if:
   - aggregate score drops beyond a small tolerance (ask the user for the tolerance if not obvious, default suggestion: any statistically meaningful drop, not noise-level)
   - any example ID that previously passed now fails, regardless of aggregate movement (this catches regressions the aggregate can mask)

3. **Judge trust gating logic**: check `eval/calibration_report.md` per metric. If a metric's judge kappa is <0.6 (or no calibration report exists), that metric's failures should **warn, not block** — annotate clearly in the script and in PR comments which metrics are advisory-only. Only calibrated (≥0.6, ideally ≥0.8) judge-based metrics can fail the build.

4. **Order checks: code-based assertions first, then judge-based**, mirroring baseline-runner — fail fast on cheap checks before spending judge-call budget in CI.

5. **Write `eval/scripts/post_pr_comment.py`**: formats the comparison result (aggregate delta, regressed example IDs, per-metric breakdown, warn-only vs. blocking metrics clearly separated) and posts it as a PR comment via `gh pr comment` or the GitHub API.

6. **Write `.github/workflows/eval-gate.yml`**: triggers on `pull_request` where changed paths match `prompts/**`, `tools/**`, `agent/**` (adjust globs to the actual repo layout — check with the user if these don't match). Steps: checkout, install deps, run `compare_to_baseline.py`, run `post_pr_comment.py`, exit non-zero on any blocking failure.

7. **Before this workflow will actually execute against a live provider in CI, confirm with the user** that they're aware CI runs will incur real API cost per PR, and get their go-ahead on the expected frequency/cost.

## Rules

- Never let an uncalibrated or poorly-calibrated (<0.6 kappa) judge block a merge — warn only, and say so explicitly in the PR comment.
- A single newly-failing example that was previously passing must fail the gate even if the aggregate score improved — this is what stops silent regressions.
- Code-based checks always run before judge-based ones in the workflow.
- Flag the real API-cost implication of running this on every PR to the user before finalizing the workflow.
