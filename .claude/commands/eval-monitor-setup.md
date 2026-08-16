---
description: Configure production tracing/sampling and the prod-failure-to-golden-set triage process — produces eval/monitoring_config.md.
allowed-tools: Skill
---

Prerequisite: `eval/results/baseline.json` must exist (calibrated judges from `eval/calibration_report.md` are reused here if present). If the baseline is missing, run `/eval-run-baseline` first.

Invoke the `production-monitor-setup` skill.

Next: this is typically the last step — the eval is now wired from definition through production feedback into `eval/golden_set.jsonl`.
