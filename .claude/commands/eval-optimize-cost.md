---
description: Run model-substitution, prompt-compression, and rule-based-router cost experiments — produces eval/cost_report.md. Blocks without an approved judge calibration.
allowed-tools: Skill, Read
---

Prerequisite: `eval/calibration_report.md` must exist and show an approved judge (kappa ≥0.6, ideally ≥0.8) for any metric the experiment touches. If missing or not approved, run `/eval-calibrate` first — this command will refuse to proceed otherwise.

Invoke the `cost-optimizer` skill. It gates on the calibration report itself, but check it here too before invoking so the user isn't surprised by a mid-skill refusal.

Next: run `/eval-monitor-setup`.
