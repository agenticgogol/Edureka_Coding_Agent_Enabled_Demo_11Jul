"""Central cost calculator.

Pricing table is hardcoded to OpenAI/Cohere published pricing as of this
build (mid-2025). Prices drift — update PRICING_PER_1M below periodically.
All local models (sentence-transformers embeddings, cross-encoder rerank)
are $0 since they run on-CPU with no API cost.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# USD per 1,000,000 tokens. (prompt, completion) for chat models;
# a single rate for embedding models.
PRICING_PER_1M = {
    "gpt-4o-mini": {"prompt": 0.15, "completion": 0.60},
    "gpt-4o": {"prompt": 2.50, "completion": 10.00},
    "text-embedding-3-small": {"embedding": 0.02},
    "text-embedding-3-large": {"embedding": 0.13},
    "cohere-embed-english-v3.0": {"embedding": 0.10},
}


@dataclass
class CostBreakdown:
    embedding_usd: float = 0.0
    condense_usd: float = 0.0
    generation_usd: float = 0.0
    embedding_tokens: int = 0
    condense_prompt_tokens: int = 0
    condense_completion_tokens: int = 0
    generation_prompt_tokens: int = 0
    generation_completion_tokens: int = 0

    @property
    def total_usd(self) -> float:
        return round(self.embedding_usd + self.condense_usd + self.generation_usd, 6)

    def to_dict(self) -> dict:
        return {
            "embedding_usd": round(self.embedding_usd, 6),
            "condense_usd": round(self.condense_usd, 6),
            "generation_usd": round(self.generation_usd, 6),
            "total_usd": self.total_usd,
            "embedding_tokens": self.embedding_tokens,
            "condense_tokens": self.condense_prompt_tokens + self.condense_completion_tokens,
            "generation_tokens": self.generation_prompt_tokens + self.generation_completion_tokens,
        }


def embedding_cost(model: str, tokens: int) -> float:
    """Returns $0 for local (sentence-transformers) models, which are not
    in PRICING_PER_1M."""
    rate = PRICING_PER_1M.get(model, {}).get("embedding")
    if rate is None:
        return 0.0
    return (tokens / 1_000_000) * rate


def chat_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    rates = PRICING_PER_1M.get(model)
    if rates is None:
        return 0.0
    return (prompt_tokens / 1_000_000) * rates["prompt"] + (
        completion_tokens / 1_000_000
    ) * rates["completion"]
