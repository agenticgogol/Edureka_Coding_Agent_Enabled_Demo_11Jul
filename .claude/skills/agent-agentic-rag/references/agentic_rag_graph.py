"""Reference LangGraph topology for Agentic RAG.

Core loop (always wired when this skill is used): decide_retrieve -> retrieve
-> grade -> (rewrite_query -> retrieve, bounded) -> generate -> respond.

Optional nodes (#3-7 in SKILL.md) are included as separately-callable stubs,
each clearly marked. Wire only the ones design.md/teaching_brief.md names —
do not add them silently.

Adapt to the actual project: swap `vector_store_query`/`llm_call` for the
real `vector_store.py`/`llm_client.py` modules produced by `vector-store` and
`helper-utils`. This file is illustrative, not a drop-in module.
"""

from __future__ import annotations

from typing import TypedDict, Literal

from langgraph.graph import StateGraph, END


MAX_RETRIEVAL_ROUNDS = 2
MAX_REGENERATION_ATTEMPTS = 1


class AgenticRAGState(TypedDict, total=False):
    question: str
    rewritten_query: str
    retrieval_round: int
    regeneration_attempt: int
    retrieved_docs: list[dict]
    graded_relevant: bool
    answer: str
    grounded: bool
    abstained: bool


# ---------------------------------------------------------------------------
# Core nodes (1: agentic retrieval decisions, 2: self-grading/self-correction)
# ---------------------------------------------------------------------------

def decide_retrieve(state: AgenticRAGState) -> AgenticRAGState:
    """Capability #1 — the agent decides whether retrieval is needed at all.

    Real implementation: one LLM call classifying the question as
    knowledge-seeking vs. answerable from the conversation alone. Stubbed
    here as "always retrieve" — replace with the real decision.
    """
    state["retrieval_round"] = 0
    state["rewritten_query"] = state["question"]
    return state


def retrieve(state: AgenticRAGState) -> AgenticRAGState:
    """Call the vector store via `vector_store.query` (from `vector-store`).

    Replace `vector_store_query` with the real import, e.g.
    `from vector_store import query as vector_store_query`.
    """
    docs = vector_store_query(state["rewritten_query"], top_k=5)
    state["retrieved_docs"] = docs
    state["retrieval_round"] = state.get("retrieval_round", 0) + 1
    return state


def grade(state: AgenticRAGState) -> AgenticRAGState:
    """Capability #2 — pass/fail relevance grading of the retrieved set.

    Real implementation: one LLM call per doc (or a single batched call)
    asking "is this relevant to the question?" Stubbed here as a naive
    non-empty check — replace with the real grader.
    """
    docs = state.get("retrieved_docs", [])
    state["graded_relevant"] = bool(docs)
    return state


def rewrite_query(state: AgenticRAGState) -> AgenticRAGState:
    """Reactive query rewrite after a bad grade (still capability #2).

    Real implementation: one LLM call producing a reformulated query given
    the original question and why the last retrieval was graded poor.
    """
    state["rewritten_query"] = llm_call(
        f"Rewrite this query to retrieve better results: {state['rewritten_query']}"
    )
    return state


def generate(state: AgenticRAGState) -> AgenticRAGState:
    context = "\n\n".join(d.get("text", "") for d in state.get("retrieved_docs", []))
    state["answer"] = llm_call(
        f"Answer using only this context:\n{context}\n\nQuestion: {state['question']}"
    )
    return state


def respond(state: AgenticRAGState) -> AgenticRAGState:
    return state


def abstain(state: AgenticRAGState) -> AgenticRAGState:
    """Reached when retrieval rounds are exhausted and grading never passed."""
    state["abstained"] = True
    state["answer"] = (
        "I don't have enough reliable information to answer this confidently."
    )
    return state


def route_after_grade(state: AgenticRAGState) -> Literal["generate", "rewrite_query", "abstain"]:
    if state.get("graded_relevant"):
        return "generate"
    if state.get("retrieval_round", 0) >= MAX_RETRIEVAL_ROUNDS:
        return "abstain"
    return "rewrite_query"


# ---------------------------------------------------------------------------
# Optional nodes — wire only the ones design.md/teaching_brief.md names.
# ---------------------------------------------------------------------------

def route_retrieval_tool(state: AgenticRAGState) -> AgenticRAGState:
    """Capability #3 — multi-tool retrieval routing.

    Real implementation: one LLM call (or rule-based classifier) picking
    among 2+ retrieval tools (vector store, SQL, web search, docs API)
    based on the question. Only wire this node if #3 is in scope; otherwise
    `retrieve` above calls the single named vector store directly.
    """
    raise NotImplementedError("Wire only if design.md names multi-tool routing (#3)")


def plan_subquestions(state: AgenticRAGState) -> AgenticRAGState:
    """Capability #4 — up-front query decomposition / multi-hop planning.

    Real implementation: one LLM call producing an ordered list of
    sub-questions before any retrieval starts (IRCoT-style), each answered
    via its own retrieve/grade/generate pass and composed into a final
    answer. Distinct from `rewrite_query`, which is reactive after a bad
    grade rather than planned up front.
    """
    raise NotImplementedError("Wire only if design.md names multi-hop planning (#4)")


def rerank_context(state: AgenticRAGState) -> AgenticRAGState:
    """Capability #5 — post-retrieval reranking / context compression.

    Real implementation: a cross-encoder or LLM call reordering/pruning
    `state["retrieved_docs"]` before it reaches `generate`, to fit the
    context budget and push the most relevant chunks first. Runs between
    `retrieve` and `grade` if wired.
    """
    raise NotImplementedError("Wire only if design.md names reranking/compression (#5)")


def verify_groundedness(state: AgenticRAGState) -> AgenticRAGState:
    """Capability #6 — groundedness / citation verification.

    Real implementation: one LLM call checking each claim in
    `state["answer"]` against `state["retrieved_docs"]`; sets
    `state["grounded"]`. On `False`, route back to `generate` (bounded by
    `MAX_REGENERATION_ATTEMPTS`) or attach an explicit caveat instead of
    silently trusting the first generation pass.
    """
    raise NotImplementedError("Wire only if design.md names groundedness verification (#6)")


# Capability #7 (confidence-based abstention) reuses the `abstain` node above
# — it is also reachable directly from `verify_groundedness` if regeneration
# attempts are exhausted and the answer still isn't grounded, not only from
# the retrieval-grading path.


# ---------------------------------------------------------------------------
# Graph assembly — core loop only. Add optional nodes/edges per the ASCII
# diagram in SKILL.md when their capability is in scope.
# ---------------------------------------------------------------------------

def build_graph() -> StateGraph:
    graph = StateGraph(AgenticRAGState)
    graph.add_node("decide_retrieve", decide_retrieve)
    graph.add_node("retrieve", retrieve)
    graph.add_node("grade", grade)
    graph.add_node("rewrite_query", rewrite_query)
    graph.add_node("generate", generate)
    graph.add_node("respond", respond)
    graph.add_node("abstain", abstain)

    graph.set_entry_point("decide_retrieve")
    graph.add_edge("decide_retrieve", "retrieve")
    graph.add_edge("retrieve", "grade")
    graph.add_conditional_edges(
        "grade",
        route_after_grade,
        {"generate": "generate", "rewrite_query": "rewrite_query", "abstain": "abstain"},
    )
    graph.add_edge("rewrite_query", "retrieve")
    graph.add_edge("generate", "respond")
    graph.add_edge("respond", END)
    graph.add_edge("abstain", END)
    return graph


def vector_store_query(query: str, top_k: int) -> list[dict]:
    """Placeholder — replace with the real `vector_store.query` import."""
    raise NotImplementedError("Wire to vector_store.py produced by the vector-store skill")


def llm_call(prompt: str) -> str:
    """Placeholder — replace with the real `llm_client.py` call import."""
    raise NotImplementedError("Wire to llm_client.py produced by the helper-utils skill")
