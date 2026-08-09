# Stage 2: Design Pattern

## Topology (from stage 1): Single-Agent

## Decision walkthrough

1. **Dominant knowledge requirement?** → **No external knowledge base — dynamic tool use over local files.** The agent doesn't need live business data from a DB/API, nor a document corpus requiring citation-style retrieval. It needs to iteratively search and read code files across 3 synthetic repos, where *which* files matter depends entirely on what the incident text says and what's found while reading — this is dynamic tool use, not fixed retrieval.

2. **Bounded tool loop or up-front plan decomposition?** → Already answered by stage 1: **bounded**. The tool space is small and fixed (repo/file search, test runner, mocked Jira client, gated patch writer), and no step has a hard dependency on a *plan* being fully decomposed before execution starts — the agent can search, read, reason, and act step by step, deciding its next tool call based on what it just observed.

Applying the decision table: steps are dynamic (which repo, which file, what the root cause is — all discovered, not knowable in advance) and the tool space is bounded → **bounded ReAct agent**.

## Chosen pattern

**Bounded ReAct agent** — one agent loop that alternates reasoning and tool calls, with a fixed toolset and a step ceiling, and a hard interrupt before any repo-mutating action.

```text
                         ┌─────────────────────────────┐
                         │   Streamlit UI (free text)   │
                         └───────────────┬───────────────┘
                                         │ incident description
                                         ▼
                         ┌─────────────────────────────┐
                         │        FastAPI backend        │
                         └───────────────┬───────────────┘
                                         │
                                         ▼
                 ┌───────────────────────────────────────────┐
                 │         Bounded ReAct Agent (LangGraph)     │
                 │                                              │
                 │   [reason] ──▶ [search_repos]  (read)        │
                 │      ▲              │                        │
                 │      │              ▼                        │
                 │      └──────── [read_file]     (read)        │
                 │      ▲              │                        │
                 │      │              ▼                        │
                 │      └──── classify: code-issue | infra-issue │
                 │                      │                        │
                 │         ┌────────────┴────────────┐           │
                 │         ▼                          ▼          │
                 │  [draft patch +           [inform user:        │
                 │   mock Jira ticket]         infra/admin]        │
                 │         │                                      │
                 │         ▼                                      │
                 │  ═══ INTERRUPT: human approval ═══              │
                 │         │ approved                              │
                 │         ▼                                      │
                 │  [apply_patch]   (write, gated)                 │
                 │         │                                      │
                 │         ▼                                      │
                 │  [run_tests]     (execute)                     │
                 │         │ pass                                 │
                 │         ▼                                      │
                 │  [close_jira_ticket]                            │
                 └───────────────────────────────────────────┘
```

Every tool call (`search_repos`, `read_file`, `run_tests`, `apply_patch`, mocked Jira create/close) is chosen by the agent one step at a time based on what it has read so far — that's the "React" loop. It's "bounded" because the toolset is fixed and small, and a step ceiling (set in stage 7) prevents runaway loops; the human-approval interrupt before `apply_patch` is the hard gate carried forward from stage 1's irreversible-action flag.

## Rejected alternatives

- **Fixed workflow (deterministic graph, no tool loop)** — rejected: this would require knowing in advance which repo and which file are relevant, but repo identification is itself dynamic (no repo hint is given; the agent must search to find it). A fixed sequence can't express "keep reading until you find the culprit."
- **Planner-executor** — rejected: this pattern earns its cost when subtasks have real dependencies that must be decomposed *before* execution (e.g. "step 3 needs step 1's output structured a specific way, and step 2 can't start until step 1's plan is validated"). Here, every step here is the same primitive (search → read → reason more) — there's nothing to decompose up front that isn't already handled by the ReAct loop's own iterative search, so the added planning overhead isn't justified.

## Model/provider notes (non-gating)

Single OpenAI model for the whole loop (e.g. a capable reasoning-tier model like `gpt-4o` or `gpt-4.1`, resolved via `_shared/llm_client.py`) — no per-role split needed since there's only one role. Classification (code vs. infra) and patch drafting both benefit from the same strong reasoning capability the root-cause search needs, so splitting to a cheaper model for classification would risk lower-quality triage for a task explicitly framed as replacing senior-engineer judgment.

## Status: APPROVED
