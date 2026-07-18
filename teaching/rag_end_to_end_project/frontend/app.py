"""Streamlit frontend for the full end-to-end RAG teaching demo.

Chat window (Claude/ChatGPT-style) backed by the FastAPI backend in
../backend. A "+" expander lets the user attach zero-to-many files and/or
a URL for ingestion. A sidebar exposes live-editable pipeline settings
(chunking, embedding, search mode/k, reranking, prompt template,
observability), the latest eval-metrics panel, and running session cost.
Query answering streams interim pipeline steps live via /query/stream's
NDJSON response, rendered inside a st.status() block.

No API keys are ever collected here — the backend owns all provider
credentials via its own .env. This UI only sends pipeline configuration
choices.
"""
from __future__ import annotations

import json
import uuid

import requests
import streamlit as st

BACKEND_URL = "http://localhost:8000"

st.set_page_config(page_title="RAG End-to-End Demo", page_icon="📚", layout="wide")
st.title("📚 RAG End-to-End Teaching Demo")

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []  # list of {"role", "content", optional extras}
if "session_total_cost_usd" not in st.session_state:
    st.session_state.session_total_cost_usd = 0.0
if "ingestion_cost_usd" not in st.session_state:
    st.session_state.ingestion_cost_usd = 0.0  # cumulative, this session
if "qna_cost_usd" not in st.session_state:
    st.session_state.qna_cost_usd = 0.0  # cumulative, this session
if "last_eval_metrics" not in st.session_state:
    st.session_state.last_eval_metrics = None
if "last_answer_cost" not in st.session_state:
    st.session_state.last_answer_cost = None

# ---------------------------------------------------------------------------
# Sidebar: pipeline settings (live-editable at any time)
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("Pipeline settings")

    st.subheader("Chunking (applies to ingestion)")
    chunking_strategy = st.selectbox(
        "Chunking strategy",
        options=["recursive", "character", "token", "semantic"],
        index=0,
    )
    chunk_size = st.number_input("Chunk size", min_value=50, max_value=4000, value=1000, step=50)
    chunk_overlap = st.number_input("Chunk overlap", min_value=0, max_value=1000, value=200, step=50)

    st.subheader("Embedding")
    embedding_model = st.selectbox(
        "Embedding model",
        options=["openai-small", "cohere", "bge-large", "minilm"],
        index=0,
    )

    st.subheader("Retrieval / search")
    search_mode = st.selectbox("Search mode", options=["hybrid", "semantic"], index=0)
    metadata_filter_raw = st.text_input(
        "Metadata filter (JSON, optional)",
        value="",
        help='e.g. {"source": "secret.txt"}',
    )
    k = st.selectbox("k (chunks to retrieve)", options=[3, 5, 10, 20, 50], index=3)
    reranking = st.selectbox("Reranking", options=["cross-encoder", "none"], index=0)

    st.subheader("Prompt template")
    custom_prompt = st.text_area(
        "Custom prompt template (optional, leave blank for backend default)",
        value="",
        help="Use {context} and {question} placeholders.",
    )

    st.subheader("Observability")
    observability_enabled = st.checkbox("Phoenix observability enabled", value=True)

    st.divider()
    st.header("Session cost")
    st.metric("Running session total (USD)", f"${st.session_state.session_total_cost_usd:.6f}")
    st.caption(
        "Includes both ingestion (embedding) and Q&A (query embedding + "
        "condense + generation) costs, tracked server-side per session."
    )
    st.markdown(
        f"- Ingestion so far: ${st.session_state.ingestion_cost_usd:.6f}\n"
        f"- Q&A so far: ${st.session_state.qna_cost_usd:.6f}"
    )

    st.divider()
    st.header("Observability")
    try:
        obs_resp = requests.get(f"{BACKEND_URL}/observability/status", timeout=10)
        obs_resp.raise_for_status()
        obs = obs_resp.json()
        mode = obs.get("mode")
        if mode == "phoenix-remote":
            st.success("Connected to Phoenix Cloud / remote collector.")
            st.markdown(f"[Open Phoenix dashboard]({obs.get('phoenix_collector_endpoint')})")
        elif mode == "phoenix-local":
            st.info("Using local Phoenix.")
            st.markdown("[Open local Phoenix dashboard](http://localhost:6006)")
        else:
            st.warning("Not connected to Phoenix.")
            st.caption(obs.get("description", ""))
    except requests.exceptions.RequestException:
        st.caption("Could not reach backend to check observability status.")

    st.divider()
    st.header("Eval metrics (latest answer)")
    if st.session_state.last_eval_metrics:
        for name, score in st.session_state.last_eval_metrics.items():
            st.write(f"**{name}**: {score:.3f}")
    else:
        st.caption("No answer generated yet.")

    if st.session_state.last_answer_cost:
        st.caption(
            "Last answer cost: "
            f"${st.session_state.last_answer_cost.get('total_usd', 0):.6f} "
            f"(embedding {st.session_state.last_answer_cost.get('embedding_tokens', 0)} tok, "
            f"generation {st.session_state.last_answer_cost.get('generation_tokens', 0)} tok)"
        )

    st.divider()
    if st.button("Reset session"):
        try:
            requests.post(f"{BACKEND_URL}/reset/{st.session_state.session_id}", timeout=30)
        except requests.exceptions.RequestException:
            pass
        st.session_state.messages = []
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.session_total_cost_usd = 0.0
        st.session_state.ingestion_cost_usd = 0.0
        st.session_state.qna_cost_usd = 0.0
        st.session_state.last_eval_metrics = None
        st.session_state.last_answer_cost = None
        st.rerun()
    st.caption("Clears only this session's documents/history.")

    st.divider()
    st.subheader("⚠️ Clear entire vector database")
    st.caption(
        "Wipes ALL ingested documents across EVERY session (not just this "
        "one) — useful when repeated testing has left stale documents "
        "behind. This cannot be undone."
    )
    confirm_clear_all = st.checkbox("I understand this deletes everything", key="confirm_clear_all")
    if st.button("Clear vector database", disabled=not confirm_clear_all):
        try:
            resp = requests.post(f"{BACKEND_URL}/admin/clear_all", timeout=60)
            resp.raise_for_status()
            cleared = resp.json().get("collections_cleared", [])
            st.session_state.messages = []
            st.session_state.session_id = str(uuid.uuid4())
            st.session_state.session_total_cost_usd = 0.0
            st.session_state.ingestion_cost_usd = 0.0
            st.session_state.qna_cost_usd = 0.0
            st.session_state.last_eval_metrics = None
            st.session_state.last_answer_cost = None
            st.success(f"Cleared: {', '.join(cleared) if cleared else 'nothing to clear'}")
            st.rerun()
        except requests.exceptions.RequestException as e:
            st.error(f"Could not clear vector database: {e}")

    st.caption(f"Session ID: `{st.session_state.session_id}`")
    st.caption(
        "To browse stored chunks directly, open your cluster at "
        "cloud.qdrant.io → Collections → `rag_demo_<embedding_model>` → Points."
    )


def _render_answer_extras(extras: dict):
    """Renders the retrieved/reranked chunks, citations, cost breakdown,
    and eval metrics for one answer — used both right after a live query
    and when replaying chat history, so this detail survives a rerun
    instead of vanishing once the st.status() block that first showed it
    collapses."""
    pre_chunks = extras.get("pre_rerank_chunks") or []
    reranked_chunks = extras.get("retrieved_chunks") or []
    reranked = extras.get("reranked", False)

    if pre_chunks:
        with st.expander(f"Retrieved chunks ({len(pre_chunks)}) — vector search order"):
            _render_chunk_list(pre_chunks, score_key="score")
    if reranked and reranked_chunks:
        with st.expander(f"Reranked chunks ({len(reranked_chunks)}) — cross-encoder order"):
            _render_chunk_list(reranked_chunks, score_key="rerank_score")

    citations = extras.get("citations") or []
    if citations:
        with st.expander(f"Sources ({len(citations)})"):
            for c in citations:
                st.markdown(
                    f"**{c['marker']}** `{c['source']}` "
                    f"(chunk {c.get('chunk_index')})\n\n"
                    f"> {c['snippet']}"
                )

    cost = extras.get("cost") or {}
    if cost:
        with st.expander(f"Cost for this answer: ${cost.get('total_usd', 0):.6f}"):
            st.markdown(
                "| Stage | Tokens | Cost (USD) |\n"
                "|---|---|---|\n"
                f"| Query embedding | {cost.get('embedding_tokens', 0)} | "
                f"${cost.get('embedding_usd', 0):.6f} |\n"
                f"| Condense (context) | {cost.get('condense_tokens', 0)} | "
                f"${cost.get('condense_usd', 0):.6f} |\n"
                f"| Generation | {cost.get('generation_tokens', 0)} | "
                f"${cost.get('generation_usd', 0):.6f} |\n"
                f"| **Total** | | **${cost.get('total_usd', 0):.6f}** |"
            )

    eval_metrics = extras.get("eval_metrics") or {}
    if eval_metrics:
        metrics_line = " | ".join(f"{name}: {score:.3f}" for name, score in eval_metrics.items())
        st.caption(f"Eval: {metrics_line}")


def _render_chunk_list(chunks: list[dict], score_key: str):
    for i, c in enumerate(chunks, start=1):
        text = " ".join(c.get("text", "").split())
        snippet = text[:220] + ("..." if len(text) > 220 else "")
        score = c.get(score_key)
        score_str = f"{score:.4f}" if isinstance(score, (int, float)) else "n/a"
        st.markdown(f"**{i}.** `{c.get('source', 'unknown')}` (chunk {c.get('chunk_index')}, score {score_str})")
        st.caption(snippet)


def _parse_metadata_filter(raw: str):
    raw = raw.strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        st.sidebar.error("Metadata filter is not valid JSON — ignoring it.")
        return None


# ---------------------------------------------------------------------------
# "+" ingestion control
# ---------------------------------------------------------------------------

with st.expander("➕ Attach files / URL to ingest"):
    uploaded_files = st.file_uploader(
        "Files (PDF or text, zero-to-many)",
        accept_multiple_files=True,
        type=["pdf", "txt", "md"],
    )
    ingest_url = st.text_input("URL (optional)", value="", key="ingest_url_input")

    if st.button("Ingest"):
        if not uploaded_files and not ingest_url.strip():
            st.warning("Provide at least one file or a URL to ingest.")
        else:
            files_payload = []
            for f in uploaded_files or []:
                files_payload.append(("files", (f.name, f.getvalue())))

            form_data = {
                "session_id": st.session_state.session_id,
                "chunking_strategy": chunking_strategy,
                "chunk_size": str(chunk_size),
                "chunk_overlap": str(chunk_overlap),
                "embedding_model": embedding_model,
            }
            if ingest_url.strip():
                form_data["url"] = ingest_url.strip()

            with st.spinner("Ingesting..."):
                try:
                    resp = requests.post(
                        f"{BACKEND_URL}/ingest",
                        data=form_data,
                        files=files_payload if files_payload else None,
                        timeout=180,
                    )
                    resp.raise_for_status()
                    result = resp.json()

                    status_lines = ["**Ingestion complete:**"]
                    for src in result["sources"]:
                        status_lines.append(
                            f"- `{src['source']}`: {src['chunks_created']} chunks created"
                        )
                    status_lines.append(f"- Total chunks: {result['total_chunks']}")
                    status_lines.append(
                        f"- Cost: {result['cost']['embedding_tokens']} embedding tokens, "
                        f"${result['cost']['embedding_usd']:.6f}"
                    )
                    st.session_state.messages.append(
                        {"role": "assistant", "content": "\n".join(status_lines)}
                    )
                    st.session_state.session_total_cost_usd = result["session_total_cost_usd"]
                    st.session_state.ingestion_cost_usd += result["cost"]["embedding_usd"]
                    st.success("Ingestion complete.")
                    st.rerun()
                except requests.exceptions.HTTPError as e:
                    try:
                        detail = e.response.json().get("detail", str(e))
                    except Exception:
                        detail = str(e)
                    st.error(f"Ingestion failed: {detail}")
                except requests.exceptions.RequestException as e:
                    st.error(f"Could not reach backend: {e}")

# ---------------------------------------------------------------------------
# Chat history
# ---------------------------------------------------------------------------

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("extras"):
            _render_answer_extras(msg["extras"])

# ---------------------------------------------------------------------------
# Chat input -> streamed query
# ---------------------------------------------------------------------------

user_input = st.chat_input("Ask a question about the ingested content...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    payload = {
        "session_id": st.session_state.session_id,
        "message": user_input,
        "embedding_model": embedding_model,
        "search_mode": search_mode,
        "k": k,
        "reranking": reranking,
        "prompt_template": custom_prompt.strip() or None,
        "observability_enabled": observability_enabled,
        "metadata_filter": _parse_metadata_filter(metadata_filter_raw),
    }

    with st.chat_message("assistant"):
        answer_text = None
        final_payload = None
        try:
            with st.status("Running RAG pipeline...", expanded=True) as status_box:
                resp = requests.post(
                    f"{BACKEND_URL}/query/stream",
                    json=payload,
                    stream=True,
                    timeout=180,
                )
                resp.raise_for_status()

                final_payload = None
                for line in resp.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    event = json.loads(line)
                    stage = event.get("stage")

                    if stage == "final":
                        final_payload = event
                        status_box.update(label="Pipeline complete", state="complete")
                        break
                    elif stage == "error":
                        status_box.update(label="Pipeline error", state="error")
                        st.error(event.get("detail", "Unknown error"))
                        break
                    elif stage == "retrieved_chunks":
                        # st.status() is itself expander-like — a nested
                        # st.expander inside it raises StreamlitAPIException,
                        # so render as a plain labeled section instead.
                        with status_box:
                            st.markdown(f"**Retrieved chunks ({len(event['chunks'])}) — vector search order**")
                            _render_chunk_list(event["chunks"], score_key="score")
                    elif stage == "reranked_chunks":
                        with status_box:
                            st.markdown(f"**Reranked chunks ({len(event['chunks'])}) — cross-encoder order**")
                            _render_chunk_list(event["chunks"], score_key="rerank_score")
                    else:
                        status_box.write(f"**{stage}**: {event.get('detail', '')}")

            if final_payload is not None:
                answer_text = final_payload["answer"]
                st.markdown(answer_text)
                _render_answer_extras(final_payload)

                eval_metrics = final_payload.get("eval_metrics") or {}
                cost = final_payload.get("cost") or {}
                st.session_state.last_eval_metrics = eval_metrics
                st.session_state.last_answer_cost = cost
                st.session_state.qna_cost_usd += cost.get("total_usd", 0)
                st.session_state.session_total_cost_usd = final_payload.get(
                    "session_total_cost_usd", st.session_state.session_total_cost_usd
                )
        except requests.exceptions.HTTPError as e:
            try:
                detail = e.response.json().get("detail", str(e))
            except Exception:
                detail = str(e)
            answer_text = f"Error: {detail}"
            st.error(answer_text)
        except requests.exceptions.RequestException as e:
            answer_text = f"Error: could not reach backend ({e})"
            st.error(answer_text)

    if answer_text is not None:
        stored_msg = {"role": "assistant", "content": answer_text}
        if final_payload is not None:
            stored_msg["extras"] = {
                "pre_rerank_chunks": final_payload.get("pre_rerank_chunks"),
                "retrieved_chunks": final_payload.get("retrieved_chunks"),
                "reranked": final_payload.get("reranked", False),
                "citations": final_payload.get("citations"),
                "cost": final_payload.get("cost"),
                "eval_metrics": final_payload.get("eval_metrics"),
            }
        st.session_state.messages.append(stored_msg)
        st.rerun()
