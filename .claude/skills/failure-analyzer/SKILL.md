---
name: failure-analyzer
description: MUST USE right after eval/results/baseline.json (or any eval run) shows failures — "why did the eval fail", "analyze failures", "failure report", "what's going wrong". Always run after baseline-runner produces results, and after any subsequent re-run. Trigger eagerly on any mention of diagnosing, clustering, or explaining eval failures — never just report a pass/fail count and stop.
---

# Failure Analyzer

Produces `eval/failure_report.md`. Clusters failures by root cause — never lists them one by one.

## Steps

1. **Read `eval/results/baseline.json`** (or the relevant results file) and pull every failing/low-scoring example, with its inputs, outputs, and grader notes.

2. **Check for regressions vs. the prior run FIRST.** If a previous results file exists, diff pass/fail status per example ID. Any example that passed before and fails now is a regression — flag it as its own top-ranked category, always listed first in the report. This is the Whack-a-Mole signal: a fix for one failure silently breaking a previously-working case. Do not bury this among the other categories.

3. **Cluster the remaining failures by root cause**, checking each of these categories and only including ones with actual hits:
   - policy/faithfulness violations
   - dropped sub-issues (multi-intent tasks where part of the request was ignored)
   - vague deferral (agent punts instead of answering/acting)
   - tool-call errors (wrong tool, bad args, missed call)
   - tone mismatch
   - retrieval miss (RAG-shaped tasks)
   - trajectory/looping (repeats steps, doesn't converge)

4. **If more than 30 failing examples**, delegate the clustering/categorization work to the `failure-triage` subagent rather than doing it inline — hand it the failing examples and this category list, and have it return the clustered breakdown.

5. **Write `eval/failure_report.md`** with, per category (regressions first):
   - count
   - % of total failures
   - example IDs
   - suggested fix direction (one or two sentences — a hypothesis, not a full fix)

## Rules

- Never present failures as a flat list — clustering by root cause is the entire point of this skill.
- Regressions vs. prior run are always their own category, always ranked first, even if small in count.
- Only delegate to failure-triage above the 30-example threshold — for smaller sets, do the clustering directly so context isn't lost to a subagent handoff.
- Suggested fix directions are hypotheses for the user to evaluate, not auto-applied changes — this skill diagnoses, it does not edit the agent's prompt/code itself.
