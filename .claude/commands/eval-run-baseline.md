---
description: Generate the promptfoo/Ragas config and run the baseline eval — produces eval/results/baseline.json.
allowed-tools: Skill
---

Prerequisite: `eval/judge_prompts/` must exist (at least an index). If missing, run `/eval-write-judge` first.

Invoke the `baseline-runner` skill. Remember: this makes real provider calls — confirm call count and approximate cost with the user before executing, per this repo's API-spend policy.

Next: run `/eval-analyze`.
