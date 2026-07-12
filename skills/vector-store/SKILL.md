---
name: vector-store
description: Use when design.md/teaching_brief.md calls for a vector database (RAG-style retrieval) and names ChromaDB, FAISS, or Qdrant Cloud. Scaffolds the chosen store's client, ingestion, and query calls — never substitutes a different store than the one named.
---

# Vector Store

One skill covering the three vector stores this repo supports, so ingestion
and query code is consistent regardless of which one a brief picks.

## When to use

- Any project/concept/teaching build whose brief/design names a vector
  database for retrieval (RAG). The choice is always explicit — never
  default to one silently if the brief/design didn't name it; that's what
  `clarify-requirements`/`teaching-brief`'s vector-DB question is for.

## Procedure

1. Confirm which store was chosen — `chromadb`, `faiss`, or `qdrant` (cloud).
   Do not substitute; if the brief says Qdrant, FAISS is not "close enough."
2. Add the dependency via `pick-requirements`:
   - ChromaDB: `chromadb` (local, on-disk persistence by default — no
     external service required, good default for teaching/local demos).
   - FAISS: `faiss-cpu` (pure local, in-memory or saved index file — no
     network dependency at all, fastest to demo, no persistence service).
   - Qdrant Cloud: `qdrant-client` + requires `QDRANT_URL` and
     `QDRANT_API_KEY` env vars (add to `.env.example` and document in
     `require-api-key`-style: these are a hard stop too if missing, same
     as the LLM provider key — a RAG demo can't run without its store).
3. Scaffold via `helper-utils`' pattern — one small module (e.g.
   `vector_store.py`) with two functions only: `upsert(chunks, embeddings,
   metadata)` and `query(embedding, top_k)`. Callers (ingestion pipeline,
   retrieval step) never touch the client SDK directly.
4. Embeddings: use whatever `design.md` names (commonly an OpenAI small
   embedding model); if unspecified, ask rather than silently picking one
   — embedding dimension must match what the store's collection/index is
   created with.
5. No mock mode: Qdrant Cloud calls are real network calls against a real
   cluster — if `QDRANT_URL`/`QDRANT_API_KEY` are missing or the connection
   fails, that's a hard stop (same treatment as a missing LLM key), not a
   fallback to local. ChromaDB/FAISS need no external service, so they have
   nothing to "mock" — they're real and local by construction.
6. Document in `data/README.md` (or the teaching demo's README): which
   store, what's ingested, the collection/index name, and how to reset it
   (delete the local ChromaDB/FAISS file, or the Qdrant collection) if a
   demo needs to re-ingest from scratch.
