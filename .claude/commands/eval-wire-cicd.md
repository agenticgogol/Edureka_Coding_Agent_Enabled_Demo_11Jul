---
description: Wire the eval into CI as a PR gate — produces .github/workflows/eval-gate.yml + comparison scripts.
allowed-tools: Skill
---

Prerequisite: `eval/results/baseline.json` must exist (and `eval/calibration_report.md` is strongly recommended, so the gate knows which judges are trustworthy). If the baseline is missing, run `/eval-run-baseline` first.

Invoke the `cicd-integrator` skill. Uncalibrated judges (no calibration report, or kappa <0.6) will warn rather than block in the resulting gate.

Next: run `/eval-optimize-cost` and/or `/eval-monitor-setup`.
