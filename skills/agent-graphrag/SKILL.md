---
name: agent-graphrag
description: Use when design.md/project_brief.md explicitly names GraphRAG (knowledge-graph-based retrieval) — distinct from standard vector-based Agentic RAG. Do not silently substitute plain vector RAG.
---

# Agent (GraphRAG)

GraphRAG retrieves via a knowledge graph (entities + relationships) instead
of (or in addition to) vector similarity. This repo's gap analysis flags
this as a named, distinct syllabus sub-topic that must not be silently
replaced by "agentic RAG" using plain vector search.

## When to use

- Brief/design names GraphRAG or knowledge-graph-based retrieval
  explicitly.

## Procedure

1. **Research-first**: fetch current docs for whichever graph library
   `design.md` selects (e.g. `networkx` for a lightweight local demo,
   or a graph-RAG-specific library) — confirm the entity/relationship
   extraction and graph-query API before writing code.
2. Read and adapt `references/basic_graphrag.py` — builds a small knowledge
   graph from source text (entity + relationship extraction via LLM),
   then answers a question by traversing the graph rather than pure
   vector similarity.
3. Keep this genuinely distinct from a vector RAG pipeline: the retrieval
   step must involve graph traversal (neighbors, paths between entities),
   not just an embedding lookup relabeled as "graph."
4. Route LLM calls (entity extraction, answer synthesis) through the copied
   `llm_client.py` — real provider only, no mock mode.
5. Expose one clean entrypoint (`answer_with_graphrag(question) -> answer`).
6. In `run-and-verify`, demonstrate a query that specifically benefits from
   multi-hop graph traversal (e.g. "how are X and Y related") — a query
   answerable by plain vector search doesn't prove GraphRAG is doing
   anything different.
