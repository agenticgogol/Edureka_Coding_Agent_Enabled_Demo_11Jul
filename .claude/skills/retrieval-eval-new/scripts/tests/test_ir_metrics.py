from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ir_metrics import mrr, ndcg_at_k, recall_at_k


def test_recall_at_k_known_value() -> None:
    retrieved = ["d1", "d2", "d3", "d4", "d5"]
    relevant = {"d2", "d5", "d9"}  # d9 never retrieved
    assert recall_at_k(retrieved, relevant, k=5) == pytest.approx(2 / 3)


def test_recall_at_k_smaller_k_excludes_later_hits() -> None:
    retrieved = ["d1", "d2", "d3"]
    relevant = {"d3"}
    assert recall_at_k(retrieved, relevant, k=2) == 0.0
    assert recall_at_k(retrieved, relevant, k=3) == 1.0


def test_recall_at_k_empty_relevant_raises() -> None:
    with pytest.raises(ValueError):
        recall_at_k(["d1"], set(), k=1)


def test_mrr_first_hit_at_rank_one() -> None:
    assert mrr(["d1", "d2"], {"d1"}) == 1.0


def test_mrr_first_hit_at_rank_three() -> None:
    assert mrr(["d9", "d8", "d1"], {"d1"}) == pytest.approx(1 / 3)


def test_mrr_no_hit_returns_zero() -> None:
    assert mrr(["d9", "d8"], {"d1"}) == 0.0


def test_ndcg_perfect_ranking_is_one() -> None:
    relevance = {"d1": 3, "d2": 2, "d3": 1}
    retrieved = ["d1", "d2", "d3"]
    assert ndcg_at_k(retrieved, relevance, k=3) == pytest.approx(1.0)


def test_ndcg_reversed_ranking_is_less_than_one() -> None:
    relevance = {"d1": 3, "d2": 2, "d3": 1}
    retrieved = ["d3", "d2", "d1"]
    score = ndcg_at_k(retrieved, relevance, k=3)
    assert 0.0 < score < 1.0


def test_ndcg_unlisted_doc_treated_as_zero_relevance() -> None:
    relevance = {"d1": 1}
    retrieved = ["dX", "d1"]  # dX not in relevance dict
    score = ndcg_at_k(retrieved, relevance, k=2)
    assert 0.0 < score <= 1.0


def test_ndcg_no_positive_relevance_raises() -> None:
    with pytest.raises(ValueError):
        ndcg_at_k(["d1"], {"d1": 0}, k=1)
