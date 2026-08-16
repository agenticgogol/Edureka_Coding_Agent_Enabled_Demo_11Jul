"""Cost/rate controls: per-incident token budget, per-key rate limiting,
and an exact-match embedding cache.

Fixes the gap flagged in the production-readiness review: step ceilings
bound the *number* of tool-call loop iterations, but nothing previously
bounded token spend within that loop, deduplicated repeat embedding calls,
or limited how often one caller could hit the API. This module is
intentionally in-process/in-memory (no Redis) — correct for a single
backend process teaching demo; a multi-process production deployment would
need a shared store (Redis INCR/EXPIRE) instead, noted inline below.
"""
from __future__ import annotations

import hashlib
import threading
import time
from collections import defaultdict, deque
from contextvars import ContextVar

from .config import MAX_TOKENS_PER_INCIDENT, RATE_LIMIT_PER_MINUTE, RATE_LIMIT_WINDOW_SECONDS


class TokenBudgetExceededError(RuntimeError):
    """Raised when one incident's cumulative LLM token usage exceeds
    MAX_TOKENS_PER_INCIDENT. Ends that incident's run rather than letting a
    stuck analysis loop burn unbounded tokens within the step ceiling."""


class RateLimitExceededError(RuntimeError):
    """Raised by check_rate_limit() when a caller has exceeded
    RATE_LIMIT_PER_MINUTE requests in the trailing window."""


# --- Per-incident token budget (contextvar: set once per start_incident/
# resume_incident call in interface.py, read by every llm.py call site
# without threading a parameter through analyze/classify/draft_patch) -----

_current_budget: ContextVar["_Budget | None"] = ContextVar("_current_budget", default=None)


class _Budget:
    __slots__ = ("limit", "used")

    def __init__(self, limit: int):
        self.limit = limit
        self.used = 0

    def add(self, tokens: int) -> None:
        self.used += tokens
        if self.used > self.limit:
            raise TokenBudgetExceededError(
                f"incident exceeded token budget: used {self.used} tokens, "
                f"limit is {self.limit} (INCIDENT_AGENT_MAX_TOKENS_PER_INCIDENT)"
            )


class incident_budget:
    """Context manager wrapping one start_incident/resume_incident call.

    Usage: `with incident_budget():` around the graph invocation in
    interface.py. Every llm.py call inside that block reports its token
    usage to record_tokens(), which raises TokenBudgetExceededError once
    the incident's cumulative usage crosses the configured cap.
    """

    def __init__(self, limit: int | None = None):
        self.limit = limit if limit is not None else MAX_TOKENS_PER_INCIDENT
        self._token = None

    def __enter__(self) -> "incident_budget":
        self._token = _current_budget.set(_Budget(self.limit))
        return self

    def __exit__(self, *exc_info) -> None:
        _current_budget.reset(self._token)


def record_tokens(tokens: int) -> None:
    """Call after every real LLM/embedding response with its total token
    usage. No-op if called outside an `incident_budget()` block (e.g. the
    one-off seed_data script), so this never breaks non-request call sites."""
    budget = _current_budget.get()
    if budget is not None:
        budget.add(tokens)


# --- Per-key rate limiting (sliding window, in-memory) ----------------------
#
# Keyed by API key (see auth.py) so one caller can't starve others.
# In-memory + a lock: correct for a single backend process. A
# multi-process/multi-instance deployment needs a shared counter (e.g.
# Redis `INCR key; EXPIRE key window`) instead of this deque-per-key
# approach — flagged here rather than silently left as a scaling trap.

_request_log: dict[str, deque[float]] = defaultdict(deque)
_rate_lock = threading.Lock()


def check_rate_limit(key: str) -> None:
    """Raises RateLimitExceededError if `key` has already made
    RATE_LIMIT_PER_MINUTE requests within the trailing
    RATE_LIMIT_WINDOW_SECONDS. Otherwise records this request and returns."""
    now = time.monotonic()
    cutoff = now - RATE_LIMIT_WINDOW_SECONDS
    with _rate_lock:
        log = _request_log[key]
        while log and log[0] < cutoff:
            log.popleft()
        if len(log) >= RATE_LIMIT_PER_MINUTE:
            raise RateLimitExceededError(
                f"rate limit exceeded: {RATE_LIMIT_PER_MINUTE} requests per "
                f"{RATE_LIMIT_WINDOW_SECONDS}s for this API key"
            )
        log.append(now)


# --- Exact-match embedding cache --------------------------------------------
#
# The same incident_text is embedded twice per submit today (once by
# search_similar_incidents for the precedent check, once by
# interface._record_incident for storage) — this cache collapses that to
# one real API call. Also absorbs accidental duplicate submissions/retries
# of literally the same text. Deliberately exact-match only (a hash of the
# normalized text), not semantic — a semantic cache would risk silently
# reusing a stale embedding for a meaningfully different incident.

_embedding_cache: dict[str, list[float]] = {}
_embedding_cache_lock = threading.Lock()
_EMBEDDING_CACHE_MAX_ENTRIES = 1000


def _cache_key(model: str, text: str) -> str:
    normalized = text.strip()
    return hashlib.sha256(f"{model}\n{normalized}".encode("utf-8")).hexdigest()


def get_cached_embedding(model: str, text: str) -> list[float] | None:
    with _embedding_cache_lock:
        return _embedding_cache.get(_cache_key(model, text))


def store_cached_embedding(model: str, text: str, vector: list[float]) -> None:
    with _embedding_cache_lock:
        if len(_embedding_cache) >= _EMBEDDING_CACHE_MAX_ENTRIES:
            # Cheapest possible eviction for an in-memory teaching-demo
            # cache: drop an arbitrary entry rather than tracking LRU order.
            _embedding_cache.pop(next(iter(_embedding_cache)))
        _embedding_cache[_cache_key(model, text)] = vector
