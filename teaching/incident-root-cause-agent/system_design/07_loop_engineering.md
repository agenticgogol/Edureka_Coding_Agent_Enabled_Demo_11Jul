# Stage 7: Loop Engineering

## Applicability

Applicable — stage 2 chose a bounded ReAct agent, which is a dynamic tool-calling loop and needs explicit control-flow discipline.

## Step ceiling

**12 tool calls for the analysis leg (precedent check through patch draft / infra decision), 3 tool calls for the execution leg (apply → test → close), 15 total per incident.**

Reasoning: worst case with no precedent match — `search_similar_incidents` (1) + `list_repos` (1) + `search_code` across up to 3 repos while narrowing down (up to 4) + `read_file` on a handful of candidate files (up to 4) + `draft_patch` (1) = 11, rounded up to 12 for margin. With a precedent match, the same ceiling still applies but the agent should typically finish in far fewer steps (precedent tells it the repo/file directly, skipping most of `list_repos`/`search_code`). The execution leg is fixed-shape (`apply_patch`, `run_tests`, `close_jira_ticket`) so 3 is exact, not a margin estimate.

## Termination conditions

1. **Infra-issue resolution** — root cause identified, classified as infra/setup, user informed with a recommendation to check with the system admin. Terminal, successful.
2. **Code-issue drafted, awaiting approval** — root cause identified, classified as code issue, patch drafted, mocked ticket created. Not terminal — this is the interrupt pause point (see below), not a failure or a success yet.
3. **Approved patch, tests pass** — after human approval, `apply_patch` → `run_tests` passes → `close_jira_ticket`. Terminal, successful.
4. **Approved patch, tests fail** — after human approval, `apply_patch` → `run_tests` fails. Not immediately terminal: the agent gets **one** `draft_patch` retry with the failing test output added to context, producing a revised patch. A revised patch is a *new* proposal and re-enters the human-approval interrupt (it was never auto-reapplied) — it does not silently retry `apply_patch` on the same diff. If the retried patch also fails validation, or the human rejects the revised proposal, the loop terminates with the ticket left open and an explicit "automated fix attempt failed test validation" note — not silently closed, not a third attempt.
5. **Patch rejected by human** — loop ends, ticket stays open, rejection note recorded (no test run, no retry — a human's explicit "no" is honored as-is, not treated as something to route around).
6. **Step ceiling exceeded without reaching any of the above** — see "Ceiling-exceeded behavior" below.

## Retry policy

| Failure type | Policy |
|---|---|
| Transient tool failure (e.g. file-read error, similarity-search backend hiccup) | Fixed 2 retries with short backoff, then treat as a hard tool failure and escalate per ceiling-exceeded behavior if it blocks progress |
| Malformed tool-call output from the model (bad arguments, invalid JSON) | 1 retry with the specific parsing error fed back into context as a correction prompt — not a blind re-ask |
| Post-approval test failure (`run_tests` fails after `apply_patch`) | 1 `draft_patch` retry as described in termination condition 4 above — re-enters human approval, not auto-applied; no further retries after that |
| Anything else unexpected | No blind retry — surface as an error state to the human via the same escalation path as ceiling-exceeded |

No unbounded retries anywhere in this design — every failure path has a fixed, small retry count and a defined next state.

## Human-in-the-loop interrupt points

Cross-checked against stage 4's tool authorization table: exactly one tool was marked "human approval required" — `apply_patch`. This is the loop's only mandatory interrupt:

- **Interrupt location**: immediately after `draft_patch` and `create_jira_ticket` complete (termination condition 2 above), before `apply_patch` is ever called. The graph pauses here, checkpointed per stage 3/5, for however long the human takes to review.
- **Resume paths**: approve → proceed to `apply_patch`; reject → terminate per condition 5; (after a post-approval test-failure retry) the revised patch re-triggers this same interrupt, it is never skipped on a retry.

No other tool in stage 4's inventory requires a pause — `search_similar_incidents`, `list_repos`, `search_code`, `read_file`, `run_tests`, `draft_patch`, `create_jira_ticket`, and `close_jira_ticket` all proceed automatically within the loop's normal flow.

## Ceiling-exceeded behavior

**Explicit escalation with partial state, not a best-effort guess.** If 12 analysis-leg tool calls are exhausted without reaching a classification, the loop stops and surfaces to the human/UI: "could not confidently determine root cause within the step budget," along with whatever partial findings exist (repos searched, files read, any leading hypothesis) — the incident record captures this as an explicit incomplete state, not a forced patch or a forced infra classification. This matches the demo's own framing (replacing senior-engineer judgment) — a senior engineer who genuinely can't figure it out says so rather than guessing, and the agent should model that same honesty rather than being pushed toward a low-confidence answer by an artificial requirement to always produce one.

## Replanning policy (if applicable)

Not applicable — stage 2 chose bounded ReAct, not planner-executor; there's no up-front plan to revise, only the step-by-step reasoning loop and the single retry paths already covered above.

## Status: APPROVED
