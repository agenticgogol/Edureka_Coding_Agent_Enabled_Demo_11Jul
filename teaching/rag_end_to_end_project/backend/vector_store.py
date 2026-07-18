"""Qdrant Cloud vector store wrapper.

Design choice: ONE SHARED collection per embedding model
(`rag_demo_{embedding_choice}`), with `session_id` stored as a payload
field and every query filtered on it. Rationale: collections in Qdrant
Cloud are a heavier-weight resource than payload filters, and demo
sessions are short-lived and numerous (every "new chat" from the
frontend is a fresh session_id) — a per-session collection would leak
collections over time with no cleanup path. A shared collection keyed by
embedding model (since vector dimensionality differs per embedding
choice) plus a `session_id` payload filter gives isolation between
sessions without collection sprawl. `reset_session` deletes points by
filter rather than dropping a collection.

Hybrid search approach: Qdrant's full sparse-vector hybrid pipeline is
more infrastructure than a teaching demo needs. As a pragmatic stand-in
documented here per the spec: "hybrid" mode runs the dense vector search
as normal, then boosts the score of any candidate whose payload text
contains the raw query as a case-insensitive keyword match (a simple
dense+keyword blend), giving a lightweight approximation of hybrid
search without standing up sparse vectors. "semantic" mode is dense-only
with no keyword boost.
"""
from __future__ import annotations

import uuid

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

from .config import config
from .embeddings import embedding_dimension

_client: QdrantClient | None = None


def get_client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(url=config.qdrant_url, api_key=config.qdrant_api_key)
    return _client


def collection_name(embedding_choice: str) -> str:
    return f"rag_demo_{embedding_choice}"


def ensure_collection(embedding_choice: str) -> str:
    name = collection_name(embedding_choice)
    client = get_client()
    existing = {c.name for c in client.get_collections().collections}
    if name not in existing:
        client.create_collection(
            collection_name=name,
            vectors_config=qm.VectorParams(
                size=embedding_dimension(embedding_choice), distance=qm.Distance.COSINE
            ),
        )
        # Qdrant Cloud requires an explicit payload index before a field can
        # be used in a query filter — session_id is filtered on every
        # search/upsert-adjacent call, so index it at collection creation.
        client.create_payload_index(
            collection_name=name, field_name="session_id", field_schema=qm.PayloadSchemaType.KEYWORD
        )
        client.create_payload_index(
            collection_name=name, field_name="source", field_schema=qm.PayloadSchemaType.KEYWORD
        )
    return name


def upsert_chunks(
    session_id: str,
    embedding_choice: str,
    chunks: list[str],
    embeddings: list[list[float]],
    metadata: list[dict],
) -> int:
    """metadata is a list of per-chunk dicts (source, chunk_index, ...),
    same length as chunks/embeddings. Returns number of points upserted."""
    if not chunks:
        return 0
    name = ensure_collection(embedding_choice)
    client = get_client()
    points = []
    for text, vector, meta in zip(chunks, embeddings, metadata):
        payload = {"session_id": session_id, "text": text, **meta}
        points.append(qm.PointStruct(id=str(uuid.uuid4()), vector=vector, payload=payload))
    client.upsert(collection_name=name, points=points)
    return len(points)


def search(
    session_id: str,
    embedding_choice: str,
    query_embedding: list[float],
    k: int = 20,
    search_mode: str = "hybrid",
    query_text: str | None = None,
    metadata_filter: dict | None = None,
) -> list[dict]:
    """Returns a list of {text, score, ...payload} sorted by score desc."""
    name = collection_name(embedding_choice)
    client = get_client()

    must = [qm.FieldCondition(key="session_id", match=qm.MatchValue(value=session_id))]
    if metadata_filter:
        for key, value in metadata_filter.items():
            must.append(qm.FieldCondition(key=key, match=qm.MatchValue(value=value)))
    query_filter = qm.Filter(must=must)

    # Over-fetch a bit when hybrid mode needs to re-rank by keyword boost.
    fetch_limit = k * 3 if search_mode == "hybrid" and query_text else k

    try:
        results = client.query_points(
            collection_name=name,
            query=query_embedding,
            query_filter=query_filter,
            limit=fetch_limit,
            with_payload=True,
        ).points
    except Exception:
        # Collection may not exist yet if nothing has been ingested for
        # this embedding choice — treat as "no results" rather than error.
        return []

    hits = [{"score": r.score, **(r.payload or {})} for r in results]

    if search_mode == "hybrid" and query_text:
        query_lower = query_text.lower()
        for hit in hits:
            if query_lower and query_lower in str(hit.get("text", "")).lower():
                hit["score"] += 0.1  # keyword-match boost, approximating hybrid
        hits.sort(key=lambda h: h["score"], reverse=True)

    return hits[:k]


_ALL_COLLECTIONS = ["rag_demo_openai-small", "rag_demo_cohere", "rag_demo_bge-large", "rag_demo_minilm"]


def delete_session(session_id: str) -> None:
    client = get_client()
    for name in _ALL_COLLECTIONS:
        try:
            client.delete(
                collection_name=name,
                points_selector=qm.FilterSelector(
                    filter=qm.Filter(
                        must=[qm.FieldCondition(key="session_id", match=qm.MatchValue(value=session_id))]
                    )
                ),
            )
        except Exception:
            pass  # collection for that embedding choice was never created


def delete_all() -> list[str]:
    """Wipes every point in every collection this demo uses, across all
    sessions — used by the sidebar's destructive "clear vector database"
    action, distinct from delete_session's per-session scope. Returns the
    list of collection names that were actually cleared (collections that
    were never created for this Qdrant Cloud cluster are skipped)."""
    client = get_client()
    cleared = []
    existing = {c.name for c in client.get_collections().collections}
    for name in _ALL_COLLECTIONS:
        if name not in existing:
            continue
        try:
            client.delete(
                collection_name=name,
                points_selector=qm.FilterSelector(filter=qm.Filter(must=[])),
            )
            cleared.append(name)
        except Exception:
            pass
    return cleared
