"""Retrieval + reranking pipeline, with a step-by-step trace for the
frontend's "interim pipeline steps" display.

Reranking options (selected per request via `reranking`):
- "cross-encoder" (default): local sentence-transformers CrossEncoder,
  model cross-encoder/ms-marco-MiniLM-L-6-v2. No paid API. Lazy-loaded
  and cached once per process.
- "none": skip reranking, keep vector-search order.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .embeddings import embed
from .vector_store import search

SUPPORTED_RERANKERS = ["cross-encoder", "none"]
ALLOWED_K = [3, 5, 10, 20, 50]

_cross_encoder = None


def _get_cross_encoder():
    global _cross_encoder
    if _cross_encoder is None:
        from sentence_transformers import CrossEncoder

        _cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    return _cross_encoder


@dataclass
class RetrievalResult:
    chunks: list[dict] = field(default_factory=list)  # final order (post-rerank if reranked)
    pre_rerank_chunks: list[dict] = field(default_factory=list)  # vector-search order, before reranking
    reranked: bool = False
    trace: list[str] = field(default_factory=list)
    query_embedding_tokens: int = 0
    query_embedding_model: str = ""


def retrieve(
    session_id: str,
    query: str,
    embedding_choice: str = "openai-small",
    search_mode: str = "hybrid",
    k: int = 20,
    reranking: str = "cross-encoder",
    metadata_filter: dict | None = None,
) -> RetrievalResult:
    trace: list[str] = []

    trace.append(f"embedding query ({embedding_choice})")
    outcome = embed([query], embedding_choice)
    query_vector = outcome.vectors[0]

    trace.append(f"searching Qdrant ({search_mode}, k={k})")
    hits = search(
        session_id=session_id,
        embedding_choice=embedding_choice,
        query_embedding=query_vector,
        k=k,
        search_mode=search_mode,
        query_text=query,
        metadata_filter=metadata_filter,
    )
    trace.append(f"{len(hits)} chunks retrieved")
    pre_rerank_chunks = [dict(h) for h in hits]  # snapshot vector-search order before any mutation
    reranked = False

    if reranking == "cross-encoder" and hits:
        trace.append("reranking with cross-encoder")
        encoder = _get_cross_encoder()
        pairs = [(query, hit.get("text", "")) for hit in hits]
        scores = encoder.predict(pairs)
        for hit, score in zip(hits, scores):
            hit["rerank_score"] = float(score)
        hits.sort(key=lambda h: h["rerank_score"], reverse=True)
        trace.append(f"{len(hits)} chunks after rerank")
        reranked = True
    elif reranking not in SUPPORTED_RERANKERS:
        raise ValueError(f"Unsupported reranking: {reranking!r}. Supported: {SUPPORTED_RERANKERS}")
    else:
        trace.append("reranking skipped (reranking=none)")

    return RetrievalResult(
        chunks=hits,
        pre_rerank_chunks=pre_rerank_chunks,
        reranked=reranked,
        trace=trace,
        query_embedding_tokens=outcome.tokens,
        query_embedding_model=outcome.model_name,
    )
