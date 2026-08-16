---
description: Scaffold a toy demo agent (Mode A) with seeded bugs to practice the eval toolkit against.
argument-hint: [archetype: support | rag | classifier | tool-using]
allowed-tools: Skill
---

Prerequisite: `eval/state.md` must exist. If missing, run `/eval-suite-init` first.

Invoke the `demo-agent-scaffolder` skill. If `$ARGUMENTS` names an archetype (support, rag, classifier, tool-using), pass it through as the chosen archetype; otherwise let the skill ask the user which archetype to use.

This is Mode A — use it instead of `/eval-integrate` when there's no existing agent in the repo to evaluate, and the goal is a practice/teaching target.
