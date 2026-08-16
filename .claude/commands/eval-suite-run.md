---
description: Run (or resume) the full 12-step eval pipeline end to end, delegated to the eval-architect subagent.
argument-hint: [demo | integrate] [fast-forward]
allowed-tools: Agent
---

Delegate the entire run to the `eval-architect` subagent with these instructions:

- **Init if needed.** If `eval/state.md` is absent, scaffold the `eval/` folder structure and an empty `eval/state.md` first (same layout as `/eval-suite-init`).

- **Mode selection.** If `$ARGUMENTS` contains "demo", set Mode A and proceed straight to `demo-agent-scaffolder` — skip asking. If `$ARGUMENTS` contains "integrate", set Mode B and proceed straight to `integration-scanner` — skip asking. Otherwise, ask the user which mode they want before continuing.

- **Run all 12 steps in order**, using each step's underlying skill/subagent exactly as it works standalone:
  1. task-definition
  2. metric-definition
  3. golden-dataset-builder
  4. grader-selector
  5. judge-prompt-builder
  6. baseline-runner
  7. failure-analyzer (or failure-triage subagent if >30 failures)
  8. judge-calibrator (via judge-calibration subagent)
  9. simulation-builder + simulation-orchestrator — **only if at least one task in eval/tasks.md is multi-turn/stateful**; otherwise mark this step skipped with a reason
  10. cicd-integrator
  11. cost-optimizer — **only if a judge is approved** (kappa ≥0.6 per eval/calibration_report.md); otherwise mark skipped with a reason and suggest running `/eval-calibrate` later
  12. production-monitor-setup

- **After every step**, update `eval/state.md`'s Pipeline Progress checklist and append a Decisions Log entry (date, step, artifact produced, key decisions), and narrate to the user what was just produced (file path + one-line summary) before moving to the next step.

- **Respect every skill's own user-review pause.** "Run everything" means continuity of state and no re-explaining context between steps — it does NOT mean skipping the review points built into task-definition, metric-definition, golden-dataset-builder, grader-selector, judge-prompt-builder, or the human-score pause in judge-calibration. Those pauses still happen exactly as they would standalone.

- **Unless `$ARGUMENTS` contains "fast-forward"**, pause at each of those review points as normal. **If "fast-forward" is present**, proceed through review points on best judgment without waiting for the user, but log every assumption made in place of a user decision to the Decisions Log, clearly marked (e.g. "ASSUMED: kept all 8 draft tasks as proposed, no user edits"). Real-money steps (baseline run, simulation run, any live provider call) still require an explicit cost go-ahead even in fast-forward mode — never skip cost approval.

- **Finish with a summary** covering:
  - a table of every artifact produced and its file path
  - the baseline aggregate score (and per-task/per-metric if notable)
  - calibration status per judge (approved/not, kappa value)
  - a one-line "what to do next" recommendation

- **On re-invocation**, read `eval/state.md` first, summarize what's already done, and resume from the first unchecked step rather than restarting.
