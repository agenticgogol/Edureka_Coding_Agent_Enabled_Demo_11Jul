---
name: production-monitor-setup
description: MUST USE when the user wants to monitor the agent in production — "production monitoring", "trace production traffic", "LangFuse", "LangSmith", "eval/monitoring_config.md", "catch new failures in prod". Run once the agent is deployed and a baseline/calibrated judge exists. Trigger eagerly on any mention of tracing, observability, or sampling production traffic for an already-evaluated agent.
---

# Production Monitor Setup

Produces `eval/monitoring_config.md`.

## Steps

1. **Pick a tracing tool by stack fit:**
   - **LangFuse** — low-friction default, use unless something below fits better
   - **LangSmith** — if the agent is built on LangChain/LangGraph
   - **Arize or Braintrust** — if the user needs enterprise-grade observability/experimentation features beyond basic tracing

   Ask the user about their stack and scale if it's not already clear from the project; don't default silently if there's a reasonable case for a non-default pick.

2. **Define sampling rate.** Recommend a starting rate (e.g. 100% for low-volume agents, 5-10% for high-volume) and note this should scale with traffic and cost tolerance — ask the user for expected volume if unknown.

3. **Reuse the SAME calibrated judge prompts** from `eval/judge_prompts/` (per `eval/calibration_report.md`) to score sampled production traces — do not write new judge prompts for production; consistency with the offline eval is the point. If a judge isn't calibrated, flag its production scores as advisory-only, same rule as cicd-integrator.

4. **Specify the triage process** for routing genuine new failures back into the golden set: sampled trace flagged low-scoring by the judge → human review confirms it's a real, novel failure (not a judge error or duplicate of an existing golden-set case) → appended to `eval/golden_set.jsonl` with `category: past_failure`, `source: production`. Write this as an explicit step-by-step process in the config, not just a mention.

5. **Include a scheduled re-baseline.** Providers update models silently server-side even when the user pins a model string; specify a recurring cadence (e.g. weekly or biweekly) to re-run baseline-runner against production-sampled inputs and diff against the stored baseline, specifically to catch silent provider-side model drift.

6. **Write `eval/monitoring_config.md`** covering: chosen tool + rationale, sampling rate + rationale, judge reuse policy, triage process for feeding golden_set.jsonl, and the re-baseline schedule.

## Rules

- Never introduce a separate judge prompt for production scoring — reuse the calibrated one, or explicitly mark scores advisory if uncalibrated.
- The triage-to-golden-set process must always require human confirmation before an example is appended — sampled failures aren't auto-added.
- Always include the scheduled re-baseline — silent model drift is the specific failure mode this guards against, don't skip it as "nice to have."
