"""FastAPI backend for the full end-to-end RAG teaching demo.

Endpoints:
- POST /ingest              — multipart: session_id, optional files, optional url,
                               chunking/embedding config -> ingestion result + cost.
- POST /query/stream         — JSON: session_id, message, pipeline config ->
                               NDJSON stream of pipeline-stage events, ending
                               with a "final" event containing the answer,
                               eval metrics, cost, and updated history.
- POST /query                — JSON, same request shape as /query/stream, but
                               synchronous: returns trace + answer + eval +
                               cost + history in one response (for callers
                               that don't want to consume a stream).
- GET  /health
- POST /reset/{session_id}
- GET  /session/{session_id}/cost

Streaming decision: real streaming (option a from the brief) was chosen
for /query/stream, using FastAPI's StreamingResponse with newline-delimited
JSON events, one per pipeline stage (condense -> embed query -> search ->
retrieved -> rerank -> generating -> final). This gives the frontend true
live interim-step visibility rather than a client-side faked reveal.
/query is kept as a synchronous convenience endpoint over the exact same
pipeline logic, for simplicity/testing and any caller that prefers a
single response.
"""
from __future__ import annotations

import json
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator

from . import conversation, session_store
from .cost import CostBreakdown, chat_cost, embedding_cost
from .eval_metrics import evaluate
from .generation import (
    DEFAULT_PROMPT_TEMPLATE,
    InvalidPromptTemplateError,
    build_citations,
    generate_answer,
    validate_prompt_template,
)
from .ingestion import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE, SUPPORTED_CHUNKERS, ingest_sources
from .embeddings import SUPPORTED_EMBEDDINGS
from .observability import get_status, span
from .retrieval import ALLOWED_K, SUPPORTED_RERANKERS, retrieve
from .vector_store import delete_all, delete_session

app = FastAPI(title="RAG End-to-End Teaching Demo")


# ---------------------------------------------------------------------------
# Request/response models
# ---------------------------------------------------------------------------

class IngestSourceResponse(BaseModel):
    source: str
    chunks_created: int


class IngestResponse(BaseModel):
    session_id: str
    sources: list[IngestSourceResponse]
    total_chunks: int
    cost: dict
    session_total_cost_usd: float


class QueryRequest(BaseModel):
    session_id: str
    message: str
    embedding_model: str = "openai-small"
    search_mode: str = "hybrid"
    k: int = 20
    reranking: str = "cross-encoder"
    prompt_template: Optional[str] = None
    observability_enabled: bool = True
    metadata_filter: Optional[dict] = None

    @field_validator("embedding_model")
    @classmethod
    def _valid_embedding(cls, v):
        if v not in SUPPORTED_EMBEDDINGS:
            raise ValueError(f"embedding_model must be one of {SUPPORTED_EMBEDDINGS}")
        return v

    @field_validator("k")
    @classmethod
    def _valid_k(cls, v):
        if v not in ALLOWED_K:
            raise ValueError(f"k must be one of {ALLOWED_K}")
        return v

    @field_validator("reranking")
    @classmethod
    def _valid_reranking(cls, v):
        if v not in SUPPORTED_RERANKERS:
            raise ValueError(f"reranking must be one of {SUPPORTED_RERANKERS}")
        return v

    @field_validator("search_mode")
    @classmethod
    def _valid_search_mode(cls, v):
        if v not in ("hybrid", "semantic"):
            raise ValueError("search_mode must be 'hybrid' or 'semantic'")
        return v


class QueryResponse(BaseModel):
    session_id: str
    answer: str
    trace: list[str]
    retrieved_chunks: list[dict]
    pre_rerank_chunks: list[dict]
    reranked: bool
    citations: list[dict]
    eval_metrics: dict
    cost: dict
    session_total_cost_usd: float
    history: list[dict]


# ---------------------------------------------------------------------------
# Shared pipeline logic (used by both /query and /query/stream)
# ---------------------------------------------------------------------------

def _validate_prompt_template(req: QueryRequest) -> None:
    if req.prompt_template is not None:
        validate_prompt_template(req.prompt_template)


def _run_query_pipeline_gen(req: QueryRequest):
    """Generator that yields a dict event after each pipeline stage
    completes (true incremental streaming — each yield happens right after
    that stage's real work finishes, not buffered), then yields a final
    {"stage": "final", ...} event with the full response payload. Shared
    by both /query (which drains it fully) and /query/stream (which
    flushes each event as an NDJSON line as it's produced)."""
    cost = CostBreakdown()

    with span("condense_question", enabled=req.observability_enabled, session_id=req.session_id):
        condense = conversation.condense_question(req.session_id, req.message)
    if condense.was_condensed:
        yield {"stage": "condense_question", "detail": f"standalone query: {condense.standalone_query}"}
        cost.condense_prompt_tokens = condense.prompt_tokens
        cost.condense_completion_tokens = condense.completion_tokens
        cost.condense_usd = chat_cost(
            "gpt-4o-mini", condense.prompt_tokens, condense.completion_tokens
        )

    standalone_query = condense.standalone_query

    with span("retrieve", enabled=req.observability_enabled, session_id=req.session_id):
        retrieval_result = retrieve(
            session_id=req.session_id,
            query=standalone_query,
            embedding_choice=req.embedding_model,
            search_mode=req.search_mode,
            k=req.k,
            reranking=req.reranking,
            metadata_filter=req.metadata_filter,
        )
    for step in retrieval_result.trace:
        yield {"stage": "retrieve", "detail": step}

    # Emit the actual chunk contents (not just counts) so the frontend can
    # show students exactly what vector search returned vs. what
    # reranking reordered/kept.
    yield {"stage": "retrieved_chunks", "chunks": retrieval_result.pre_rerank_chunks}
    if retrieval_result.reranked:
        yield {"stage": "reranked_chunks", "chunks": retrieval_result.chunks}

    cost.embedding_tokens = retrieval_result.query_embedding_tokens
    cost.embedding_usd = embedding_cost(
        retrieval_result.query_embedding_model, retrieval_result.query_embedding_tokens
    )

    yield {"stage": "generating", "detail": "generating answer"}
    with span("generate", enabled=req.observability_enabled, session_id=req.session_id):
        generation = generate_answer(
            question=standalone_query,
            chunks=retrieval_result.chunks,
            prompt_template=req.prompt_template,
        )
    cost.generation_prompt_tokens = generation.prompt_tokens
    cost.generation_completion_tokens = generation.completion_tokens
    cost.generation_usd = chat_cost(
        generation.model, generation.prompt_tokens, generation.completion_tokens
    )
    yield {"stage": "answer_ready", "detail": "answer generated"}

    citations = build_citations(generation.answer, retrieval_result.chunks)

    context_texts = [c.get("text", "") for c in retrieval_result.chunks]
    with span("evaluate", enabled=req.observability_enabled, session_id=req.session_id):
        eval_scores = evaluate(standalone_query, context_texts, generation.answer)
    yield {"stage": "eval", "detail": "eval metrics computed"}

    session_store.append_turn(req.session_id, "user", req.message)
    session_store.append_turn(req.session_id, "assistant", generation.answer)

    session_total = session_store.add_cost(req.session_id, cost.total_usd)

    full_trace = (
        (["condensing follow-up question"] if condense.was_condensed else [])
        + retrieval_result.trace
        + ["generating answer", "answer generated", "computing eval metrics"]
    )

    yield {
        "stage": "final",
        "session_id": req.session_id,
        "answer": generation.answer,
        "trace": full_trace,
        "retrieved_chunks": retrieval_result.chunks,
        "pre_rerank_chunks": retrieval_result.pre_rerank_chunks,
        "reranked": retrieval_result.reranked,
        "citations": citations,
        "eval_metrics": eval_scores.to_dict(),
        "cost": cost.to_dict(),
        "session_total_cost_usd": round(session_total, 6),
        "history": session_store.get_history(req.session_id),
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/observability/status")
def observability_status() -> dict:
    return get_status()


@app.post("/ingest", response_model=IngestResponse)
async def ingest(
    session_id: str = Form(...),
    url: Optional[str] = Form(None),
    chunking_strategy: str = Form("recursive"),
    chunk_size: int = Form(DEFAULT_CHUNK_SIZE),
    chunk_overlap: int = Form(DEFAULT_CHUNK_OVERLAP),
    embedding_model: str = Form("openai-small"),
    files: list[UploadFile] = File(default=[]),
) -> IngestResponse:
    if chunking_strategy not in SUPPORTED_CHUNKERS:
        raise HTTPException(422, f"chunking_strategy must be one of {SUPPORTED_CHUNKERS}")
    if embedding_model not in SUPPORTED_EMBEDDINGS:
        raise HTTPException(422, f"embedding_model must be one of {SUPPORTED_EMBEDDINGS}")

    file_payloads: list[tuple[str, bytes]] = []
    for f in files:
        if f is None or not f.filename:
            continue
        file_payloads.append((f.filename, await f.read()))

    if not file_payloads and not url:
        raise HTTPException(422, "Provide at least one file or a url to ingest.")

    try:
        result = ingest_sources(
            session_id=session_id,
            files=file_payloads,
            url=url,
            chunking_strategy=chunking_strategy,
            embedding_choice=embedding_model,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
    except Exception as e:
        raise HTTPException(502, f"Ingestion failed: {e}")

    session_total = session_store.add_cost(session_id, result.embedding_cost_usd)

    return IngestResponse(
        session_id=session_id,
        sources=[IngestSourceResponse(source=s.source, chunks_created=s.chunks_created) for s in result.sources],
        total_chunks=result.total_chunks,
        cost={
            "embedding_tokens": result.embedding_tokens,
            "embedding_usd": round(result.embedding_cost_usd, 6),
            "total_usd": round(result.embedding_cost_usd, 6),
        },
        session_total_cost_usd=round(session_total, 6),
    )


@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest) -> QueryResponse:
    try:
        _validate_prompt_template(req)
    except InvalidPromptTemplateError as e:
        raise HTTPException(422, str(e))

    try:
        final_event = None
        for event in _run_query_pipeline_gen(req):
            if event.get("stage") == "final":
                final_event = event
    except Exception as e:
        raise HTTPException(502, f"Query pipeline failed: {e}")

    final_event.pop("stage", None)
    return QueryResponse(**final_event)


@app.post("/query/stream")
def query_stream(req: QueryRequest):
    try:
        _validate_prompt_template(req)
    except InvalidPromptTemplateError as e:
        raise HTTPException(422, str(e))

    def event_generator():
        try:
            for event in _run_query_pipeline_gen(req):
                yield json.dumps(event) + "\n"
        except Exception as e:
            yield json.dumps({"stage": "error", "detail": str(e)}) + "\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")


@app.post("/reset/{session_id}")
def reset(session_id: str) -> dict:
    session_store.clear_session(session_id)
    try:
        delete_session(session_id)
    except Exception:
        pass
    return {"status": "cleared", "session_id": session_id}


@app.get("/session/{session_id}/cost")
def session_cost(session_id: str) -> dict:
    return {"session_id": session_id, "total_usd": round(session_store.get_total_cost(session_id), 6)}


@app.post("/admin/clear_all")
def clear_all_vector_data() -> dict:
    """Wipes every point in every collection this demo uses, across every
    session — distinct from /reset/{session_id}, which only clears one
    session. Intended for the sidebar's destructive "clear vector
    database" control so repeated manual testing doesn't accumulate stale
    documents across page reloads (Streamlit keeps the same session_id
    across reloads unless Reset is clicked)."""
    cleared_collections = delete_all()
    return {"status": "cleared", "collections_cleared": cleared_collections}
