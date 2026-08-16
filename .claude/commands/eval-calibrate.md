---
description: Run the human-vs-judge Cohen's kappa calibration loop for a model-based judge — produces eval/calibration_report.md.
argument-hint: [metric name]
allowed-tools: Agent
---

Prerequisite: `eval/judge_prompts/` must exist. If missing, run `/eval-write-judge` first.

Delegate to the `judge-calibration` subagent for the metric named in `$ARGUMENTS` (if omitted, ask the user which model-based metric from `eval/graders.md` to calibrate). It samples, generates a human scoring sheet, **pauses for real human scores** (never fabricates them), computes quadratic-weighted Cohen's kappa, diagnoses disagreements, edits the judge prompt, and re-runs — up to 3 iterations before stopping and reporting a persistent pattern.

Next: once approved (kappa ≥0.6, ideally ≥0.8), run `/eval-wire-cicd` and/or `/eval-optimize-cost`.
