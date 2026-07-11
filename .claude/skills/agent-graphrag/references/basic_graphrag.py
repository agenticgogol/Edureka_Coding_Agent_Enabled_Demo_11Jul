"""Minimal GraphRAG sketch: build a small knowledge graph from text via
LLM-extracted (entity, relation, entity) triples, then answer questions by
graph traversal — genuinely distinct from vector-similarity RAG.

Install: pip install networkx. LLM calls go through llm_client.complete()
— a real, verified provider key is required (see require-api-key skill);
there is no mock mode.
"""
from __future__ import annotations

import json
from typing import Callable

import networkx as nx

# from llm_client import complete  # uncomment after copying into project


def extract_triples(text: str, llm_complete: Callable[[str], str]) -> list[tuple[str, str, str]]:
    prompt = (
        "Extract (subject, relation, object) triples from this text as a "
        "JSON list of 3-item lists. Text:\n" + text
    )
    raw = llm_complete(prompt)
    try:
        triples = json.loads(raw)
        return [tuple(t) for t in triples if len(t) == 3]
    except (json.JSONDecodeError, TypeError):
        return []


def build_graph(documents: list[str], llm_complete: Callable[[str], str]) -> nx.DiGraph:
    graph = nx.DiGraph()
    for doc in documents:
        for subject, relation, obj in extract_triples(doc, llm_complete):
            graph.add_edge(subject, obj, relation=relation)
    return graph


def answer_with_graphrag(question: str, graph: nx.DiGraph, entities_in_question: list[str]) -> str:
    """Multi-hop traversal between entities mentioned in the question —
    this is the part a plain vector-similarity RAG pipeline can't do."""
    if len(entities_in_question) < 2 or graph.number_of_nodes() == 0:
        return "Not enough graph context to answer via traversal."

    a, b = entities_in_question[0], entities_in_question[1]
    if a not in graph or b not in graph:
        return f"One or both entities ({a}, {b}) not found in graph."

    try:
        path = nx.shortest_path(graph, a, b)
    except nx.NetworkXNoPath:
        return f"No relationship path found between {a} and {b}."

    relations = [
        f"{path[i]} -[{graph[path[i]][path[i+1]]['relation']}]-> {path[i+1]}"
        for i in range(len(path) - 1)
    ]
    return " ; ".join(relations)


if __name__ == "__main__":
    from llm_client import complete  # requires a real provider key set in .env

    docs = ["Alice founded Acme Corp.", "Acme Corp acquired Beta Inc."]
    g = build_graph(docs, llm_complete=complete)
    print(answer_with_graphrag("How are Alice and Beta Inc related?", g, ["Alice", "Beta Inc"]))
