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

### One-time kernel setup (do this before running anything else)

This machine has many other Jupyter kernels registered for unrelated
projects, and the generic kernel literally named `python3` on this system
resolves to a completely different venv (`Edureka_Full_Course/venv`), not
this folder's `.venv`. Every notebook here used to carry a generic
`"name": "python3"` kernelspec, which meant opening or executing a
notebook could silently run it against the wrong Python and the wrong
installed packages (a real bug hit repeatedly while building this
series — `ModuleNotFoundError` for packages that *were* installed, just
not in the environment actually running the notebook).

Fixed by registering a dedicated, correctly-pointed kernel once, and
every notebook in this folder (and its subfolders) now references it by
name in its own `kernelspec` metadata:

```bash
cd teaching/langgraph_basics
source .venv/bin/activate
python3 -m ipykernel install --user --name=langgraph-basics --display-name="LangGraph Basics (.venv)"
```

After this, opening any notebook here in Jupyter/VS Code, or running
`jupyter execute some_notebook.ipynb` with no `--kernel` flag, will
resolve to this folder's `.venv` automatically — verify with:

```bash
jupyter kernelspec list | grep langgraph-basics
```

If you ever add a **new** notebook to this folder, either duplicate an
existing notebook (kernelspec metadata carries over) or set its kernel
explicitly in Jupyter's UI ("Kernel -> Change Kernel -> LangGraph Basics
(.venv)") before running it — do not leave a new notebook on whatever
kernel Jupyter defaults to.

To run the advanced track:

```bash
jupyter notebook langgraph_advanced.ipynb
```

To run the agent memory deep-dive (checkpointers vs. Mem0+ChromaDB
long-term memory):

```bash
jupyter notebook agent_memory_deepdive.ipynb
```

To run the agent context engineering notebook (data determinism via
strict Pydantic schemas, and token economics via context isolation +
context selection):

```bash
jupyter notebook agent_context_engineering.ipynb
```

To run the agent human-in-the-loop notebook (three HITL mechanisms —
static `interrupt_before`, dynamic `interrupt()`, and conditional
interrupts — with a clear decision rule for which one fits which
situation):

```bash
jupyter notebook agent_hitl.ipynb
```

To run the agent tool authorization notebook (four defense layers —
least-privilege binding, in-tool permission checks, injection-resistant
argument validation, and HITL — with a decision rule for which layer
catches which failure):

```bash
jupyter notebook agent_tool_authorization.ipynb
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
- **Agent memory deep-dive**: `agent_memory_deepdive.ipynb` executed top to
  bottom against the real Anthropic API (14 calls, individually approved).
  Covers `InMemorySaver` vs. `SqliteSaver` (including a genuine process
  restart proving durability), the cross-thread amnesia problem, Mem0 +
  ChromaDB long-term memory (Anthropic LLM + local HuggingFace embedder, no
  OpenAI dependency), a Mem0-alternatives comparison, and a combined
  checkpointer + long-term-memory finale. Requires `mem0ai`, `chromadb`, and
  `sentence-transformers` (added to `requirements.txt`).
- **Agent context engineering**: `agent_context_engineering.ipynb` executed
  top to bottom against the real Anthropic API (14 calls total across both
  parts, individually approved). Part 1 (data determinism) shows real
  without/with-schema failures on a support-triage agent, a calendar
  tool-call payload, and a supervisor router, then how `.with_structured_output()`
  works internally. Part 2 (token economics) shows real per-node context
  isolation via LangGraph `input_schema`, then prunes a real 10-turn
  conversation two ways (sliding token window vs. semantic relevance
  selection via the same local HuggingFace embedder as the memory
  notebook) — including an honest, unedited finding that semantic
  selection retrieves the right facts correctly but can still make the
  model *under-confident* about reasserting them from fragmented context,
  a real prompting nuance distinct from retrieval correctness. Ends with a
  full combined LangGraph agent (triage → prune → route → isolated
  specialists) tying every piece together. Requires `tiktoken` in addition
  to the memory notebook's dependencies (added to `requirements.txt`).
- **Agent human-in-the-loop**: `agent_hitl.ipynb` executed top to bottom
  against the real OpenAI API (`gpt-4o-mini`, 1 call — the rest of the
  notebook is pure LangGraph `interrupt`/`Command` mechanics, no LLM
  needed). Covers three distinct HITL mechanisms with an explicit decision
  table (static `interrupt_before`, dynamic `interrupt()`, and a
  no-LangGraph return-draft escape hatch), an approval gate on a mutating
  refund action, editable-state correction via a real (non-scripted)
  ambiguous-email extraction, configurable conditional interrupts (a
  tunable risk threshold, not hardcoded), and a combined finale showing
  both a low-risk auto-approved path and a high-risk paused-and-edited
  path through the same graph. A horizontal, architecture-agnostic
  companion to the memory and context-engineering notebooks — every
  pattern here drops into any topology in `multi_agent_architectures/`
  unchanged. Flags the single most damaging real HITL bug explicitly:
  placing side-effecting code before an `interrupt()` call inside the same
  node, since LangGraph re-runs the whole node function from the top on
  resume.
- **Agent tool authorization**: `agent_tool_authorization.ipynb` executed
  top to bottom against the real OpenAI API (`gpt-4o-mini`, ~6 calls,
  approved). Separates four distinct defense layers — least-privilege
  binding, an in-tool permission check, injection-resistant argument
  validation, and HITL — with an explicit decision table and the design
  principle that a permission check is only as strong as the
  trustworthiness of what it checks against. Part 2 blocks a real
  cross-tenant (IDOR-style) data leak using a caller identity that never
  passes through anything the LLM controls. Part 3 uses a real,
  non-scripted extraction call over a genuinely ambiguous, injected
  ticket — the model *did* fall for the injection on the executed run
  (extracted $9999.99 against a real $89.50 order total), which is kept
  as the honest result proving why the deterministic validation layer
  matters, not edited toward a cleaner story. Part 4 combines all four
  layers across four scenarios, including a nuanced real finding: a
  request Layer 3 already safely capped can still cross the HITL
  threshold, and a human reviewer correctly rejects it anyway once they
  see it originally asked for 100x the real amount — a fraud signal
  Layer 3's capping alone cannot see. A horizontal, architecture-agnostic
  companion to the memory, context-engineering, and HITL notebooks.

## Single-agent architectures series

`single_agent_architectures/` is a five-notebook deep dive on
architecture *selection* for a single agent — ReAct, Plan-Execute-Replan,
advanced self-evaluation, and when parallel or separate-context workflows are justified. See
`single_agent_architectures/README.md` for the full breakdown.

## Multi-agent architectures series

`multi_agent_architectures/` covers multi-agent topology selection —
supervisor, parallel fan-out/fan-in, sequential pipeline, planner-executor,
critic-actor, and hierarchical supervision. See
`multi_agent_architectures/README.md` for the full breakdown.

## Agent runtime operations series

`agent_runtime_operations/` is a different, orthogonal layer from the two
series above: not how an agent reasons, but how it gets invoked, scaled,
retried, and triggered in a real system — queues and async workers,
retries and idempotency, event-driven triggers, and scheduling. Every
graph from the other two series drops into every pattern here unchanged.
See `agent_runtime_operations/README.md` for the full breakdown.

## Loop engineering series

`loop_engineering/` teaches the control system around an agent: inner
observe–decide–act–verify loops, objective completion gates, work discovery,
context packaging, persistent progress, recovery, review gates, and safe
continuation. It sits between the single-agent and multi-agent architecture
series because the same loop principles apply to both. See
`loop_engineering/README.md` for the planned sequence.

## Agent evaluation series

`agent_evaluation/` covers how agents actually get evaluated — human
annotation, synthetic data generation, scripted and LLM-judge scoring,
observability tooling (Phoenix, and without), regression suites,
production monitoring, error attribution in multi-agent trajectories,
multi-turn conversational eval, pairwise/preference comparison, cost and
latency tracking, and metric validity. Uses two real agents already
built in this repo (the single-agent SRE investigator and the
multi-agent helpdesk supervisor) as consistent case studies across all
thirteen notebooks rather than a new example each time, closing with a
capstone/map notebook and an accessibility retrofit (ELI12, glossary,
checkpoint questions) on every notebook. See `agent_evaluation/README.md`
for the full breakdown.

## Notes for extending

To continue this demo later (e.g. adding an agentic-RAG step that builds on
the tool-calling/loop concepts here), use `/add-teaching-step
langgraph_basics` rather than re-running the full pipeline.
