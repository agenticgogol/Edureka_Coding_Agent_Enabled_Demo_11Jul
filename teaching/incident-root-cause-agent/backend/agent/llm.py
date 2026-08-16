"""OpenAI client wrapper for this agent module.

This repo's shared `_shared/llm_client.py` template only exposes a plain
`complete(prompt) -> str` call, with no tool/function-calling support and
no embeddings endpoint. This module's bounded-ReAct search loop needs
OpenAI tool-calling (to let the model choose `list_repos` / `search_code`
/ `read_file` / finish), and precedent search needs real embeddings — so
this module talks to the OpenAI SDK directly rather than forcing those
through the plain-text `complete()` shape. Provider selection is still
centralized (OPENAI_API_KEY only, enforced in `config.py`) and there is no
mock mode: every call here is a real OpenAI call, and failures propagate,
they are never caught and replaced with canned output.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from openai import (
    APIConnectionError,
    APITimeoutError,
    InternalServerError,
    OpenAI,
    RateLimitError,
)
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

from . import budget
from .config import (
    EMBEDDING_MODEL,
    OPENAI_MAX_RETRIES,
    OPENAI_TIMEOUT_SECONDS,
    REASONING_MODEL,
    config,
)

logger = logging.getLogger("incident_backend.llm")

_client: OpenAI | None = None

# Transient conditions worth retrying at our layer, on top of the OpenAI
# SDK's own built-in retry (see get_client(): max_retries handles a subset
# of these already). This decorator adds jittered backoff and makes the
# retry policy visible/tunable in one place instead of relying solely on
# the SDK default.
_RETRYABLE_ERRORS = (RateLimitError, APIConnectionError, APITimeoutError, InternalServerError)

_llm_retry = retry(
    retry=retry_if_exception_type(_RETRYABLE_ERRORS),
    stop=stop_after_attempt(OPENAI_MAX_RETRIES),
    wait=wait_random_exponential(multiplier=1, max=20),
    reraise=True,
)


def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=config.openai_api_key,
            timeout=OPENAI_TIMEOUT_SECONDS,
            # SDK-level retry for connection-level failures below the
            # HTTP-response layer; _llm_retry above handles the rest
            # (rate limits, 5xx, timeouts) with visible jittered backoff.
            max_retries=0,
        )
    return _client


@_llm_retry
def chat_with_tools(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    tool_choice: str | dict | None = None,
    model: str | None = None,
) -> Any:
    """Single entrypoint for every chat-completion call in this agent
    (with or without tools). Retries transient provider failures (rate
    limits, timeouts, connection errors, 5xx) with jittered exponential
    backoff up to OPENAI_MAX_RETRIES; any other error, or exhausted
    retries, propagates — never caught and replaced with canned output."""
    client = get_client()
    kwargs: dict[str, Any] = {
        "model": model or REASONING_MODEL,
        "messages": messages,
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = tool_choice or "auto"
    response = client.chat.completions.create(**kwargs)
    if response.usage:
        budget.record_tokens(response.usage.total_tokens)
    return response.choices[0].message


@_llm_retry
def complete_json(system: str, user: str, model: str | None = None) -> dict:
    """Chat completion constrained to return a single JSON object. Used
    for classification / patch drafting where a structured response is
    required before showing anything to a human for approval. Same
    transient-failure retry policy as chat_with_tools; a response that
    comes back but fails to parse as JSON is NOT retried here — the model
    was asked for `response_format=json_object`, so a parse failure is a
    real provider/model anomaly worth surfacing, not silently retried."""
    client = get_client()
    response = client.chat.completions.create(
        model=model or REASONING_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
    )
    if response.usage:
        budget.record_tokens(response.usage.total_tokens)
    content = response.choices[0].message.content
    return json.loads(content)


@_llm_retry
def _embed_uncached(text: str, model: str) -> list[float]:
    client = get_client()
    response = client.embeddings.create(model=model, input=text)
    if response.usage:
        budget.record_tokens(response.usage.total_tokens)
    return response.data[0].embedding


def embed(text: str, model: str | None = None) -> list[float]:
    """Return an embedding vector for `text`. Real OpenAI embeddings call
    — no mock/fallback vector. Exact-match cached (see budget.py) so the
    same incident_text embedded twice in one request (precedent check +
    storage) only costs one real API call."""
    resolved_model = model or EMBEDDING_MODEL
    cached = budget.get_cached_embedding(resolved_model, text)
    if cached is not None:
        return cached
    vector = _embed_uncached(text, resolved_model)
    budget.store_cached_embedding(resolved_model, text, vector)
    return vector
