# Teaching Brief: LangGraph Basics

## Description (as given by user)
Progressive LangGraph fundamentals demo, notebook format, toy data, free tools only.
Every step must include: (1) a markdown cell explaining the concept's theory —
what it is, why it exists, how LangGraph implements it, and related/adjacent
concepts that are easy to confuse with it; (2) a mermaid diagram of that
step's graph topology; (3) runnable code against the real Claude API; (4)
visible correct output demonstrating the concept.

## Steps (in order, each builds on the previous)
a) Basic StateGraph — one node, state schema, normal edges, START, END — added 2026-07-19
b) Conditional edges — added 2026-07-19
c) Loop / cycle (with termination condition) — added 2026-07-19
d) Checkpointing / memory (MemorySaver, multi-turn state persistence) — added 2026-07-19
e) Tool calling — added 2026-07-19
f) Multi-tool selection — how the LLM decides which tool to call — added 2026-07-19
g) Recursion limit — deliberately exceeded to show the resulting error — added 2026-07-19
h) Streaming (.stream() / token and event streaming) — added 2026-07-19
i) Human-in-the-loop (interrupt + resume) — added 2026-07-19
j) Subgraphs (nested graph inside a parent graph) — added 2026-07-19
k) Sequential vs parallel execution (fan-out/fan-in, timing comparison) — added 2026-07-19
l) Orchestrator-worker pattern — added 2026-07-19
m) LLM-as-node variants for steps a-d — added 2026-07-19: (a) node body is
   an LLM call instead of a string transform; (b) routing decision and
   both branches are LLM calls instead of a len() check; (c) loop is a
   real self-refinement pattern (write -> LLM judge -> loop until
   approved or max attempts) instead of a counter; (d) checkpointed node
   is a real chat node whose second turn recalls information from the
   first turn, instead of an incrementing counter

## Format
notebook

## Happy-path test case (user-approved)
User opens the notebook and runs it top to bottom. Each of the 12 steps has:
(1) a markdown cell explaining the concept's theory — what it is, why it
exists, how LangGraph implements it, and related concepts easy to confuse
with it (e.g. step b's markdown explains conditional edges and how they
differ from tool-calling-based routing introduced later in e/f); (2) a
mermaid diagram of that step's graph topology; (3) runnable code executing
against the real Claude API (model: claude-sonnet-5); (4) visible correct
output demonstrating the concept. No step throws an unhandled error, and no
tool requires a paid signup. Step g intentionally triggers and shows the
recursion-limit error as the expected outcome, not a bug.

## Observability
none

## Vector store
none

## Constraints
- Provider-swappable via an explicit flag: near the top of the notebook, a
  single visible variable (e.g. `PROVIDER = "anthropic"  # or "openai"`)
  controls which API the rest of the notebook uses — not silent
  auto-detection. A `get_llm()` helper reads that flag, pulls the matching
  key (`ANTHROPIC_API_KEY` or `OPENAI_API_KEY`) from `.env`, and fails
  loudly if that key is missing (no fallback to the other provider). Both
  paths verified working via real API calls on 2026-07-19: Anthropic
  (`claude-sonnet-5`) and OpenAI (`gpt-4o`).
- Tool roster (steps e/f), all free / no paid signup:
  - Toy calculator (local Python function)
  - Toy weather lookup (local hardcoded dict)
  - DuckDuckGo search (`duckduckgo-search` package, real, no API key)
  - Wikipedia lookup (`wikipedia` package, real, no API key)
  - Python REPL / sandboxed code execution tool (local, no key)
  - arXiv search (real, free API, no key)
- Toy/synthetic data only — no external datasets requiring download/license.
- No mock mode — every LLM call in the notebook is real.

## Audience level
Intermediate — assumes familiarity with LLMs/APIs/Python; explains
LangGraph-specific concepts in depth.

## Decisions
- User wants "some difficult/complicated" free tools in addition to
  trivial ones, hence Wikipedia/Python-REPL/arXiv added to the roster
  alongside calculator/weather/DuckDuckGo (6 tools total) — confirmed by
  user.
- Every step requires theory markdown + mermaid diagram, not just code —
  explicit user requirement, applies to all 12 steps uniformly.

## Checkpoint status
- Description: approved
- Clarifications: approved
- Format: approved
- Happy-path test case: approved
- API key verification: verified (Anthropic, claude-sonnet-5, real call succeeded 2026-07-19)
- Observability: approved (none)
- Vector store: approved (none)
- Ready to generate: approved
- Build: complete
- Verify: complete

## Advanced companion notebook

Added 2026-07-25 as a separate artifact: `langgraph_advanced.ipynb`.
It covers explicit bounded ReAct agents, complete streaming modes, tool
failure handling, structured output and validation, advanced checkpointing,
realistic human approval, subgraph state boundaries, robust async parallelism,
multi-agent patterns, and runtime context/configuration. The executed copy is
`executed_langgraph_advanced.ipynb`; it passed top-to-bottom execution against
the configured real provider with no cell errors.

The advanced companion was subsequently strengthened with an enforced
application-level agent budget, real custom and tool lifecycle streaming,
agent-integrated resilient tools, structured-output repair, file-backed SQLite
checkpoint restart and historical branching, and human-approved tool
execution; the corrected executed copy still passes with no cell errors.
