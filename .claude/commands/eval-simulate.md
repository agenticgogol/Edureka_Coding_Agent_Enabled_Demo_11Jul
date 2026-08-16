---
description: Define personas/config for multi-turn tasks, then execute the simulation runs — produces eval/simulation/.
allowed-tools: Skill, Agent
---

Prerequisite: `eval/tasks.md` must exist with at least one multi-turn/stateful task. If `eval/tasks.md` is missing, run `/eval-define-tasks` first. If no task is multi-turn/stateful, this command does not apply — skip it.

First invoke the `simulation-builder` skill to define personas, success conditions, and the simulation config under `eval/simulation/`. Once the user has reviewed and approved that config, delegate execution to the `simulation-orchestrator` subagent, which alternates simulator/SUT turns, hard-stops at the turn cap, logs full transcripts, and grades trajectories.

Remember: this makes real provider calls (simulator + SUT + judge, multiplied across personas and runs) — confirm cost with the user before executing.

Next: run `/eval-wire-cicd`.
