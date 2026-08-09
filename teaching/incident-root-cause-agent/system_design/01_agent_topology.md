# Stage 1: Agent Topology — Single vs. Multi-Agent

## Business problem (restated)
The underlying need is to compress the manual debugging judgment of an experienced senior software engineer — reading an incident report, figuring out which service/repo is responsible, tracing the root cause in code, and deciding whether it's a code bug or an infra/setup problem — into an agent that can do this confidently over a real codebase, propose a fix, and prove the fix works, with a human still approving before any code changes take effect. We're proposing to solve this with an agent; before deciding *how many*, we check whether the task actually needs more than one.

## Decision walkthrough

1. **Known steps vs. dynamic sequence?** → **Known.** The overall workflow is fixed and doesn't branch unpredictably: identify responsible repo → analyze code for root cause → classify code-issue vs. infra-issue → (code path) draft patch + mocked Jira ticket → pause for human approval → apply patch → re-run the incident's synthetic test(s) → close ticket on pass. What varies is only the *content* found while searching (which repo, which file, which function) — not the shape of the process itself. This is a single continuous task with bounded tool calls, not a task whose next step is unknowable ahead of time.

2. **Irreversible / high-impact action?** → **Yes.** Applying a patch writes to repo files, which is exactly the kind of action that shouldn't happen without a human in the loop — already specified as a hard gate. This doesn't change single vs. multi, but it's carried forward as a mandatory human-approval wrapper for stages 4, 7, and 8.

3. **If dynamic: bounded or needs-decomposition?** → **Bounded.** The tool space is small and fixed for this demo: repo/file search (read), synthetic test runner (execute), mocked Jira client (create/close ticket), patch writer (write, gated). No subtask has a real dependency on another subtask's output *before* execution starts — repo identification and root-cause analysis both use the same read-only search tool, just iteratively. A step ceiling + allowlist is sufficient; no upfront task decomposition into independent dependent subtasks is needed.

4. **Distinct specialist capabilities needing independent execution / measurable parallelism or isolation benefit?** → **No.** Repo identification, root-cause analysis, and patch drafting are all the same kind of reasoning — reading code and reasoning about it — performed sequentially by one model with tools. There's no independently-parallelizable specialist work here (e.g. no separate "security reviewer" and "performance reviewer" that must run concurrently); splitting this into multiple agents would only add routing/handoff overhead without a measurable speed or quality win.

5. **Isolation needed to prevent one wrong answer contaminating another part of the system?** → **No.** Single user, one incident processed at a time, no multi-tenant data-leakage risk (all synthetic, local, single session). There's no case here where one component's mistake needs to be walled off from another's context.

## Decision: Single-Agent

## Why
Q4 and Q5 were both **no** — there is no measurable parallelism to exploit and no isolation boundary to enforce. The task is one continuous reasoning-plus-tool-use loop (search → diagnose → branch → propose → wait for approval → apply → verify → close), which is exactly what a single bounded agent with a fixed toolset is for.

## Rejected alternative
**Multi-agent** (e.g. a separate "repo locator" agent handing off to a "root cause analyst" agent handing off to a "patch writer" agent) was considered, given how tempting it is to mirror the human workflow's distinct phases as distinct agents. It's rejected because Q4's test fails: these "phases" don't need independent execution — they share the same context (the incident description and whatever code has been read so far), the same tool type (read-only search), and there is no case where running them in parallel or isolating their context from each other would improve the answer. Splitting them would only add coordination/handoff LLM calls and more failure surface, for a task that is small and sequential enough for one agent to hold in one loop.

## Carried-forward signals for later stages
- High-impact/irreversible action: **yes** — patch application (write to repo files) requires a hard human-approval gate before it happens; carry this into stage 4 (tool authorization), stage 7 (loop/interrupt design), and stage 8 (guardrails).
- Sub-branch (single-agent): **bounded** — small, fixed tool allowlist (repo search, test runner, mocked Jira client, gated patch writer) with a step ceiling, not upfront task decomposition.

## Status: APPROVED
