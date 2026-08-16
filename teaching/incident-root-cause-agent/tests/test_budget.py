"""Unit tests for backend/agent/budget.py — token budget, rate limiter,
embedding cache. No real API calls anywhere in this file."""
from __future__ import annotations

import pytest

from backend.agent import budget


class TestIncidentBudget:
    def test_raises_once_limit_exceeded(self):
        with budget.incident_budget(limit=100):
            budget.record_tokens(60)
            with pytest.raises(budget.TokenBudgetExceededError):
                budget.record_tokens(50)

    def test_does_not_raise_under_limit(self):
        with budget.incident_budget(limit=100):
            budget.record_tokens(30)
            budget.record_tokens(30)
            # 60 < 100, no raise

    def test_record_tokens_is_noop_outside_any_context(self):
        # Regression guard: interface.py relies on this being safe so that
        # _record_incident()'s embed() call (which happens AFTER the
        # incident_budget() block exits) never raises even if the budget
        # was already exceeded during the graph invocation.
        budget.record_tokens(10**9)  # must not raise

    def test_budget_scoped_per_context_not_leaked_across(self):
        with budget.incident_budget(limit=10):
            budget.record_tokens(5)
            # exiting here should reset — a second, unrelated context
            # must not inherit the first one's usage.
        with budget.incident_budget(limit=10):
            budget.record_tokens(9)  # would have raised if usage leaked (5+9=14>10)

    def test_nested_nonoverlapping_contexts_do_not_interfere(self):
        with budget.incident_budget(limit=5):
            with pytest.raises(budget.TokenBudgetExceededError):
                budget.record_tokens(6)
        # outer context has exited too (single `with`), so this is a fresh one
        with budget.incident_budget(limit=100):
            budget.record_tokens(50)  # fine


class TestRateLimiter:
    def test_allows_up_to_configured_limit_then_blocks(self):
        from backend.agent.config import RATE_LIMIT_PER_MINUTE

        key = "test-key-exact"
        for _ in range(RATE_LIMIT_PER_MINUTE):
            budget.check_rate_limit(key)  # must not raise
        with pytest.raises(budget.RateLimitExceededError):
            budget.check_rate_limit(key)

    def test_different_keys_have_independent_limits(self):
        from backend.agent.config import RATE_LIMIT_PER_MINUTE

        for _ in range(RATE_LIMIT_PER_MINUTE):
            budget.check_rate_limit("key-a")
        # key-b's window is independent — must not raise
        budget.check_rate_limit("key-b")

    def test_window_expiry_allows_new_requests(self, monkeypatch):
        from backend.agent.config import RATE_LIMIT_PER_MINUTE

        key = "test-key-expiry"
        fake_now = [1000.0]
        monkeypatch.setattr(budget.time, "monotonic", lambda: fake_now[0])

        for _ in range(RATE_LIMIT_PER_MINUTE):
            budget.check_rate_limit(key)
        with pytest.raises(budget.RateLimitExceededError):
            budget.check_rate_limit(key)

        # advance past the window
        fake_now[0] += budget.RATE_LIMIT_WINDOW_SECONDS + 1
        budget.check_rate_limit(key)  # must not raise now


class TestEmbeddingCache:
    def test_miss_then_hit(self):
        assert budget.get_cached_embedding("model-x", "some incident text") is None
        budget.store_cached_embedding("model-x", "some incident text", [1.0, 2.0, 3.0])
        assert budget.get_cached_embedding("model-x", "some incident text") == [1.0, 2.0, 3.0]

    def test_different_model_is_a_different_cache_key(self):
        budget.store_cached_embedding("model-a", "same text", [1.0])
        assert budget.get_cached_embedding("model-b", "same text") is None

    def test_exact_match_only_not_semantic(self):
        budget.store_cached_embedding("model-x", "checkout API returns 500", [1.0])
        # A different (even similar) string must NOT hit the cache — this
        # cache is deliberately exact-match to avoid silently reusing a
        # stale embedding for a meaningfully different incident.
        assert budget.get_cached_embedding("model-x", "checkout api returns 500 error") is None

    def test_whitespace_normalization(self):
        budget.store_cached_embedding("model-x", "  leading and trailing  ", [9.0])
        assert budget.get_cached_embedding("model-x", "leading and trailing") == [9.0]
