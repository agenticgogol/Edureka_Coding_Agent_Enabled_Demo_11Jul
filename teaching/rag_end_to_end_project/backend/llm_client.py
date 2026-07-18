"""OpenAI client wrapper for chat completion + embeddings.

No mock mode: every call hits the real OpenAI API using OPENAI_API_KEY
from config.py, and every response's usage field is captured for cost
tracking (see cost.py). Local (sentence-transformers) embeddings are
handled separately in ingestion.py/retrieval.py since they don't go
through OpenAI.
"""
from __future__ import annotations

from dataclasses import dataclass

from openai import OpenAI

from .config import config

DEFAULT_CHAT_MODEL = "gpt-4o-mini"
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"

_client: OpenAI | None = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=config.openai_api_key)
    return _client


@dataclass
class ChatResult:
    content: str
    prompt_tokens: int
    completion_tokens: int
    model: str


@dataclass
class EmbeddingResult:
    vectors: list[list[float]]
    tokens: int
    model: str


def chat_completion(
    messages: list[dict],
    model: str = DEFAULT_CHAT_MODEL,
    max_tokens: int | None = None,
    temperature: float = 0.2,
) -> ChatResult:
    client = get_client()
    kwargs: dict = {"model": model, "messages": messages, "temperature": temperature}
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    response = client.chat.completions.create(**kwargs)
    usage = response.usage
    return ChatResult(
        content=response.choices[0].message.content or "",
        prompt_tokens=usage.prompt_tokens if usage else 0,
        completion_tokens=usage.completion_tokens if usage else 0,
        model=model,
    )


def embed_texts(texts: list[str], model: str = DEFAULT_EMBEDDING_MODEL) -> EmbeddingResult:
    if not texts:
        return EmbeddingResult(vectors=[], tokens=0, model=model)
    client = get_client()
    response = client.embeddings.create(model=model, input=texts)
    vectors = [item.embedding for item in response.data]
    tokens = response.usage.total_tokens if response.usage else 0
    return EmbeddingResult(vectors=vectors, tokens=tokens, model=model)
