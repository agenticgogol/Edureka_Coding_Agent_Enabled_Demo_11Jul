# LangGraph Basics

A progressive, hands-on notebook covering the LangGraph concepts needed
before building agentic RAG: StateGraph fundamentals, conditional edges,
loops, checkpointing/memory, tool calling, multi-tool selection, recursion
limits, streaming, human-in-the-loop, subgraphs, sequential vs parallel
execution, and the orchestrator-worker pattern. Every step includes a
theory explanation, a Mermaid diagram of that step's graph topology, real
runnable code, and visible output.

Steps (a) through (d) each have a second "variant" cell right after them,
showing the same graph topology with the node body replaced by a real LLM
call: an LLM-driven greeting rewrite (a), LLM-driven classification +
LLM-generated replies (b), a genuine self-refinement loop with an LLM judge
(c), and real multi-turn chat memory (d) — so the plain-function and
LLM-as-node versions of each concept sit side by side.

`langgraph_advanced.ipynb` is the companion advanced track. It covers bounded
ReAct agents, complete streaming surfaces, tool reliability, structured output,
checkpoint history and branching, realistic human approval, private subgraph
state, async parallel fan-out, multi-agent architectures, and runtime context
and permissions.

## How to run

```bash
cd teaching/langgraph_basics
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
jupyter notebook notebook.ipynb
```

To run the advanced track:

```bash
jupyter notebook langgraph_advanced.ipynb
```

Set the `PROVIDER` flag in the setup cell to `"anthropic"` or `"openai"` —
this single flag controls which API the whole notebook uses (no silent
auto-detection; the matching key must be in the repo-root `.env`).

## Verified against

- **Providers**: Anthropic (`claude-sonnet-5`) and OpenAI (`gpt-4o`) — both
  confirmed working via real API calls before build.
- **LangGraph version**: 1.2.9 (spike-tested every API used — `StateGraph`,
  conditional edges, `InMemorySaver`, `interrupt`/`Command`, `Send`,
  `ToolNode`/`tools_condition`, `GraphRecursionError` — against the actual
  installed version rather than assumed from training knowledge, since the
  library moves fast).
- **Free tools**: toy calculator, toy weather (hardcoded), DuckDuckGo
  search (`ddgs` package — note: `duckduckgo-search` is deprecated,
  renamed to `ddgs`), Wikipedia (`wikipedia` package), Python REPL (local
  sandboxed `exec`), arXiv search (`arxiv` package, uses `arxiv.Client()`,
  the current API). All free, no signup/API key required.
- **Full run**: `executed_notebook.ipynb` is the notebook executed top to
  bottom on 2026-07-19 with real output for every one of the 12 steps —
  including the deliberate `GraphRecursionError` in step (g), a real
  interrupt/resume cycle in step (i), and a measured sequential-vs-parallel
  timing difference in step (k) (~1.5s vs ~0.5s for three 0.5s tasks).
- **Observability**: none (per brief).
- **Vector store**: none — no retrieval steps in this demo.
- **Advanced verification**: `executed_langgraph_advanced.ipynb` was executed
  top to bottom against the configured real provider after implementing the
  agent budget, custom/tool event streaming, resilient agent tools, structured
  output recovery, durable SQLite checkpoints, historical branching, and
  human-approved tool execution.

## Notes for extending

To continue this demo later (e.g. adding an agentic-RAG step that builds on
the tool-calling/loop concepts here), use `/add-teaching-step
langgraph_basics` rather than re-running the full pipeline.
