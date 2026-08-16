---
description: Cluster eval failures by root cause — produces eval/failure_report.md. Routes to a subagent automatically for large failure counts.
allowed-tools: Read, Agent, Skill
---

Prerequisite: `eval/results/baseline.json` (or another results file) must exist. If missing, run `/eval-run-baseline` first.

Count the failing examples in the results file. If there are more than 30, delegate to the `failure-triage` subagent (it clusters and writes the full report, returning only a compressed top-2-3-categories summary). Otherwise, invoke the `failure-analyzer` skill directly inline.

Either path writes/updates `eval/failure_report.md`, with regressions vs. the prior run always ranked first.

Next: run `/eval-calibrate` for any metric with model-based grading before trusting its scores for gating.
