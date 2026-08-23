---
name: agent-agentic-rag
description: Use when design.md/project_brief.md/teaching_brief.md calls for Agentic RAG — retrieval where the agent itself decides whether/how/how-many-times to retrieve and checks its own output, rather than one fixed retrieve-then-generate call. Distinct from plain RAG (vector-store's fixed pipeline, no loop) and from GraphRAG (agent-graphrag, graph-traversal retrieval) — implements the loop as a LangGraph topology, not a separate framework.
---

# Agent (Agentic RAG)

Plain RAG (the `vector-store` skill wired into one fixed retrieve-then-generate
call) always retrieves exactly once and always answers with whatever came back.
Agentic RAG is that same retrieval layer wrapped in an agent loop that can
decide to retrieve again, grade what it got, reroute, or decline to answer —
built as a LangGraph state graph, using `agent-langgraph`'s own state/node/edge
conventions, not a new framework.

## When to use

- `design.md`/`project_brief.md`/`teaching_brief.md` names "Agentic RAG"
  explicitly, or `technical-design` / `agent-decision-design-pattern` detected
  and recorded it as the chosen pattern (see those skills' detection steps).
- Never silently downgrade to plain fixed-pipeline RAG once Agentic RAG is
  named — that is the same "substitution not allowed" rule this repo applies
  to every other named framework.
- Never silently substitute for `agent-graphrag`. Agentic RAG's retrieval is
  vector/tool-based; GraphRAG's is graph-traversal-based. If a design wants
  *agentic control flow over a graph retriever*, say so explicitly and treat
  it as both skills combined — don't pick one and drop the other.

## What "Agentic RAG" means here, vs plain RAG

Two capabilities are **core** — without them this is just plain RAG with
extra steps, so always include both when this skill is invoked:

1. **Agentic retrieval decisions** — the agent decides whether to retrieve at
   all, and can issue more than one retrieval round (not a single fixed call).
2. **Self-grading / self-correction** — a grading step scores the retrieved
   docs for relevance; a bad grade triggers a rewritten query and re-retrieval
   (bounded retry count), rather than generating off bad context.

The rest are **optional add-ons** — each is a real cost (extra LLM calls per
turn), so only wire the ones `design.md`'s Tech choices section names. Never
add these silently:

3. **Multi-tool retrieval routing** — a router node picks among 2+ retrieval
   tools (vector store, SQL, web search, docs API) instead of one fixed
   retriever.
4. **Query decomposition / multi-hop planning** — an up-front planning node
   breaks a complex question into an ordered sequence of sub-questions
   *before* any retrieval happens (IRCoT-style). Distinct from #2: #2 is
   reactive ("that retrieval failed, try again"), this is proactive planning
   of what needs to be known.
5. **Post-retrieval reranking / context compression** — a rerank node
   reorders or prunes the retrieved set before it reaches the generator.
   Distinct from #2's pass/fail grading — this is "keep the good parts, drop
   the noise, fit the context budget," not "retrieve again."
6. **Groundedness / citation verification** — a post-generation node checks
   each claim in the answer against the retrieved docs; an ungrounded claim
   triggers regeneration or an explicit caveat, rather than trusting the
   first generation pass.
7. **Confidence-based abstention** — the agent can end the loop with "the
   retrieved evidence is insufficient" (or a clarifying question) instead of
   always producing an answer. A fixed RAG pipeline always answers; this one
   can decline to.

## Procedure

1. Confirm with `design.md`/`teaching_brief.md` exactly which of capabilities
   3-7 are in scope, alongside the always-on core (1-2). Record the confirmed
   list before writing code — this is what `retrieval-eval-new` and
   `eval-and-observability` will later check against.
2. Wire the retrieval backend via `vector-store` (reuse its `upsert`/`query`
   functions — don't reinvent the client). If #3 (multi-tool routing) is in
   scope, the router node calls `vector-store`'s `query` as one branch among
   several, not a replacement for it.
3. Build the LangGraph state graph following `agent-langgraph`'s state/node/
   edge/checkpointing conventions. Agentic RAG is a **topology within
   LangGraph**, not a separate library:

   ```
   [decide_retrieve] -> [retrieve] -> [grade]
        |  no-retrieval path              |
        v                            bad  |  good
     [generate] <----------------- [rewrite_query] --(loop, bounded)--> [retrieve]
        |    ^                                              |
        |    | regenerate (bad groundedness)            good, retries exhausted
        v    |                                              v
   [verify_groundedness]                                [abstain]
        |
        v (grounded)
      [respond]
   ```
   Nodes for #3-7 slot into this same graph (router before `retrieve`,
   planner before the loop starts, rerank between `retrieve` and `grade`,
   groundedness/abstain as shown). See `references/agentic_rag_graph.py` for
   the reference implementation — the two core nodes are live code; each
   optional node is a clearly-marked, separately-callable stub.
4. **Bound every loop explicitly** — max retrieval rounds, max regeneration
   attempts — both as named constants in the state, not implicit recursion.
   A loop that exhausts its budget must go to `abstain` (or a caveated
   answer), never spin forever or silently return a low-quality answer.
5. Route every LLM call in the graph (grading, query rewrite, planning,
   LLM-based reranking, groundedness check, generation) through the copied
   `llm_client.py` from `helper-utils` — real provider only, no mock mode,
   same rule as every other agent skill in this repo.
6. No external RAG framework is required — this is stock LangGraph
   (`StateGraph`, conditional edges), which is already the repo's
   well-covered default, so `research-first`'s docs-check requirement does
   not apply here the way it does for CrewAI/DSPy/GraphRAG.
7. In `run-and-verify`, demonstrate at least one query that exercises the
   loop — e.g. a query whose first retrieval round is graded insufficient and
   a rewritten query succeeds. A query that always succeeds on round 1 proves
   nothing an ordinary fixed RAG pipeline wouldn't also prove.
8. Record in `design.md`/`teaching_brief.md`'s Constraints which of
   capabilities 1-7 are actually wired vs. explicitly out of scope for this
   build — `retrieval-eval-new` and `eval-and-observability` read this to
   decide which agentic-specific checks apply.

## Reference

`references/agentic_rag_graph.py` — LangGraph reference implementation: state
shape, the core decide/retrieve/grade/rewrite loop as runnable code, and
clearly-marked optional node stubs for routing (#3), planning (#4), reranking
(#5), groundedness verification (#6), and abstention (#7).
