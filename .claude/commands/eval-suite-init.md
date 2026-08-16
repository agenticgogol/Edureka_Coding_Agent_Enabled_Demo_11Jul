---
description: Scaffold the eval/ folder structure and empty eval/state.md — the first command to run for any new eval project.
allowed-tools: Bash, Write, Read
---

Scaffold the eval toolkit's folder structure under `eval/` if it doesn't already exist:

```
eval/results/
eval/judge_prompts/
eval/calibration/
eval/simulation/personas/
eval/simulation/transcripts/
eval/simulation/trajectory_judges/
eval/scripts/
```

Create these directories (use `mkdir -p` for all at once). Then, if `eval/state.md` does not already exist, create it with this skeleton:

```markdown
# Eval State

## Mode
unset

## Agent Description
(not yet set)

## Pipeline Progress
- [ ] 1. task-definition
- [ ] 2. metric-definition
- [ ] 3. golden-dataset-builder
- [ ] 4. grader-selector
- [ ] 5. judge-prompt-builder
- [ ] 6. baseline-runner
- [ ] 7. failure-analyzer
- [ ] 8. judge-calibrator
- [ ] 9. simulation-builder
- [ ] 10. cicd-integrator
- [ ] 11. cost-optimizer
- [ ] 12. production-monitor-setup

## Decisions Log
```

If `eval/state.md` already exists, do not overwrite it — report its current Mode and checklist status instead.

Prerequisite: none — this is always the first command.

Next: run `/eval-demo-agent` (Mode A, practice agent) or `/eval-integrate` (Mode B, existing agent), then `/eval-define-tasks`.
