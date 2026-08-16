---
description: Read-only scan of an existing agent already in this repo (Mode B) to seed the eval pipeline with real task candidates.
allowed-tools: Agent
---

Prerequisite: `eval/state.md` must exist. If missing, run `/eval-suite-init` first.

Delegate to the `integration-scanner` subagent to read-only scan the repo for the existing agent's system prompts, tool/function definitions, agent loop, policy docs, and any existing bug reports/logs. It writes `eval/scan_report.md` and pre-fills `eval/state.md` (Mode B).

This is Mode B — use it instead of `/eval-demo-agent` when evaluating an agent that already exists in this repo.

Next: run `/eval-define-tasks`, using `eval/scan_report.md`'s inferred task candidates as a starting point.
