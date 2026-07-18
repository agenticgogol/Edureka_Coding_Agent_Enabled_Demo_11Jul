"""Embedding provider abstraction shared by ingestion.py and retrieval.py.

Supported embedding options (selected per request via `embedding_model`):
- "openai-small" (default): OpenAI text-embedding-3-small, via llm_client.
- "cohere": Cohere embed-english-v3.0, via the `cohere` package. Requires
  COHERE_API_KEY.
- "bge-large": local, sentence-transformers BAAI/bge-large-en-v1.5.
- "minilm": local, sentence-transformers all-MiniLM-L6-v2.

Local models are lazy-loaded once per process and cached in _LOCAL_MODEL_CACHE
so repeated requests don't reload them.
"""
from __future__ import annotations

from dataclasses import dataclass

from .config import config
from .llm_client import DEFAULT_EMBEDDING_MODEL, embed_texts

SUPPORTED_EMBEDDINGS = ["openai-small", "cohere", "bge-large", "minilm"]

_LOCAL_MODEL_NAMES = {
    "bge-large": "BAAI/bge-large-en-v1.5",
    "minilm": "all-MiniLM-L6-v2",
}

_LOCAL_MODEL_CACHE: dict[str, object] = {}

_COHERE_MODEL = "embed-english-v3.0"


@dataclass
class EmbeddingOutcome:
    vectors: list[list[float]]
    tokens: int  # 0 for local models (no token cost)
    model_name: str  # pricing-table key used for cost.py, or local model id


def _get_local_model(embedding_choice: str):
    if embedding_choice not in _LOCAL_MODEL_CACHE:
        from sentence_transformers import SentenceTransformer

        _LOCAL_MODEL_CACHE[embedding_choice] = SentenceTransformer(
            _LOCAL_MODEL_NAMES[embedding_choice]
        )
    return _LOCAL_MODEL_CACHE[embedding_choice]


def embed(texts: list[str], embedding_choice: str = "openai-small") -> EmbeddingOutcome:
    if not texts:
        return EmbeddingOutcome(vectors=[], tokens=0, model_name=embedding_choice)

    if embedding_choice == "openai-small":
        result = embed_texts(texts, model=DEFAULT_EMBEDDING_MODEL)
        return EmbeddingOutcome(
            vectors=result.vectors, tokens=result.tokens, model_name=DEFAULT_EMBEDDING_MODEL
        )

    if embedding_choice == "cohere":
        config.require_cohere_key()
        import cohere

        client = cohere.Client(config.cohere_api_key)
        response = client.embed(
            texts=texts, model=_COHERE_MODEL, input_type="search_document"
        )
        vectors = list(response.embeddings)
        # Cohere's Python SDK does not return token usage on this endpoint;
        # approximate using a simple whitespace-token count for cost display.
        approx_tokens = sum(len(t.split()) for t in texts)
        return EmbeddingOutcome(
            vectors=vectors, tokens=approx_tokens, model_name="cohere-embed-english-v3.0"
        )

    if embedding_choice in _LOCAL_MODEL_NAMES:
        model = _get_local_model(embedding_choice)
        vectors = model.encode(texts, convert_to_numpy=True).tolist()
        return EmbeddingOutcome(vectors=vectors, tokens=0, model_name=_LOCAL_MODEL_NAMES[embedding_choice])

    raise ValueError(
        f"Unsupported embedding_model: {embedding_choice!r}. "
        f"Supported: {SUPPORTED_EMBEDDINGS}"
    )


def embedding_dimension(embedding_choice: str) -> int:
    """Vector size per embedding choice — needed to size the Qdrant collection."""
    return {
        "openai-small": 1536,
        "cohere": 1024,
        "bge-large": 1024,
        "minilm": 384,
    }[embedding_choice]
