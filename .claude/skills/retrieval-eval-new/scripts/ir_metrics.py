"""Retrieval-only IR metrics: Recall@k, MRR, NDCG.

Deliberately separate from evallib.stats — these operate on ranked doc lists
per query, not on binary human/judge label pairs. Kept here (skill-local,
not evallib) because they're specific to retrieval evaluation, not shared
across every skill the way evallib.stats is.

A "query result" is: the ranked list of doc_ids the retriever returned, and
the set of doc_ids that are actually relevant for that query (ground truth).
"""

from __future__ import annotations

import math
from typing import Sequence


def recall_at_k(retrieved: Sequence[str], relevant: set[str], k: int) -> float:
    """Fraction of relevant docs that appear in the top-k retrieved."""
    if k <= 0:
        raise ValueError(f"k must be positive, got {k}")
    if not relevant:
        raise ValueError("relevant set must be non-empty (undefined recall with no relevant docs)")
    top_k = set(retrieved[:k])
    return len(top_k & relevant) / len(relevant)


def mrr(retrieved: Sequence[str], relevant: set[str]) -> float:
    """Reciprocal rank of the first relevant doc in `retrieved`. 0.0 if none found."""
    if not relevant:
        raise ValueError("relevant set must be non-empty (undefined MRR with no relevant docs)")
    for rank, doc_id in enumerate(retrieved, start=1):
        if doc_id in relevant:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(
    retrieved: Sequence[str], relevance: dict[str, float], k: int
) -> float:
    """Normalized Discounted Cumulative Gain at k.

    `relevance` maps doc_id -> graded relevance score (e.g. 0/1/2/3). A
    doc_id retrieved but absent from `relevance` is treated as relevance 0
    (retrieved-but-irrelevant), not an error.
    """
    if k <= 0:
        raise ValueError(f"k must be positive, got {k}")
    if not relevance or all(v <= 0 for v in relevance.values()):
        raise ValueError("relevance must contain at least one doc with positive relevance")

    def dcg(doc_ids: Sequence[str]) -> float:
        return sum(
            relevance.get(doc_id, 0.0) / math.log2(rank + 1)
            for rank, doc_id in enumerate(doc_ids[:k], start=1)
        )

    actual = dcg(retrieved)
    ideal_order = sorted(relevance, key=lambda d: relevance[d], reverse=True)
    ideal = dcg(ideal_order)

    if ideal == 0.0:
        raise ValueError("ideal DCG is 0 (no positive relevance docs) — NDCG undefined")

    return actual / ideal
