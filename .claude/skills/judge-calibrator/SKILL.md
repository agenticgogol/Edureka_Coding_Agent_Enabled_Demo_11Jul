---
name: judge-calibrator
description: MUST USE before trusting any model-based judge's scores for gating decisions — "calibrate the judge", "is the judge trustworthy", "human vs judge agreement", "eval/calibration_report.md", "Cohen's kappa". Run once judge_prompts/ exist and before cost-optimizer or cicd-integrator rely on judge scores as a gate. Trigger eagerly whenever the user wants confidence that an LLM judge agrees with human judgment.
---

# Judge Calibrator

Produces `eval/calibration_report.md` — a human-vs-judge agreement study, never assumed, always measured.

## Steps

1. **Sample 30-50 stratified examples** from `eval/golden_set.jsonl`, stratified across tasks and categories (common/edge/past_failure) so the sample isn't dominated by one shape.

2. **Generate a human scoring sheet** (e.g. `eval/calibration/human_scoring_sheet.csv`) with the input, agent response, and the judge's scale/anchors, blank score column for a human to fill in. **Never fabricate human scores** — this step produces the sheet only; wait for the user (or a designated human rater) to actually fill it in before proceeding.

3. **Run the judge independently** on the same sampled examples using the existing prompt from `eval/judge_prompts/`, recording its scores separately from the human sheet.

4. **Once human scores are provided, compute Cohen's kappa** (quadratic weights, since these are ordinal 3-point scales) via `sklearn.metrics.cohen_kappa_score(..., weights="quadratic")`. Write/use a script under `eval/scripts/` for this so it's re-runnable.

5. **Apply thresholds:** ≥0.8 strong agreement, 0.6-0.8 substantial (usable with caution), <0.6 don't trust this judge for gating — flag it clearly.

6. **Diagnose every disagreement greater than 1 scale level** by likely cause: ambiguous rubric, missing reference material, judge bias (verbosity bias, position bias, self-preference bias), or human rater slip. Categorize each such disagreement explicitly.

7. **If kappa is below 0.8**, propose concrete edits to the judge prompt (tighter anchors, added reference material, explicit anti-bias instruction) targeting the diagnosed causes, get user approval, edit `eval/judge_prompts/<metric>.md`, and re-run the calibration on the same sample to check improvement.

8. **Write `eval/calibration_report.md`** with: sample composition, kappa score + threshold verdict, disagreement breakdown by cause, prompt edits made (if any) and resulting kappa, and a **re-check trigger**: judge prompt change, model change (SUT or judge), or 90 days elapsed — whichever comes first.

## Rules

- Never fabricate or simulate human scores under any circumstance — if no human rater is available, stop and say so; do not proceed with a fake calibration.
- Always use quadratic-weighted kappa for these ordinal scales, not plain/unweighted kappa.
- A judge below 0.6 must not be used as a pre-launch gate — say so explicitly in the report, and flag downstream skills (cost-optimizer, cicd-integrator) that depend on this judge.
- Re-check trigger must be written into the report every time, not left implicit.
