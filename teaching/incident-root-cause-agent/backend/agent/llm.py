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
from typing import Any

from openai import OpenAI

from .config import config, EMBEDDING_MODEL, REASONING_MODEL

_client: OpenAI | None = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=config.openai_api_key)
    return _client


def chat_with_tools(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    tool_choice: str | dict | None = None,
    model: str | None = None,
) -> Any:
    """Single entrypoint for every chat-completion call in this agent
    (with or without tools). Raises on any provider error — no fallback."""
    client = get_client()
    kwargs: dict[str, Any] = {
        "model": model or REASONING_MODEL,
        "messages": messages,
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = tool_choice or "auto"
    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message


def complete_json(system: str, user: str, model: str | None = None) -> dict:
    """Chat completion constrained to return a single JSON object. Used
    for classification / patch drafting where a structured response is
    required before showing anything to a human for approval."""
    client = get_client()
    response = client.chat.completions.create(
        model=model or REASONING_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content
    return json.loads(content)


def embed(text: str, model: str | None = None) -> list[float]:
    """Return an embedding vector for `text`. Real OpenAI embeddings call
    — no mock/fallback vector."""
    client = get_client()
    response = client.embeddings.create(model=model or EMBEDDING_MODEL, input=text)
    return response.data[0].embedding
