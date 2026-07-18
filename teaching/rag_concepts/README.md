# RAG Concepts

A progressive Jupyter notebook teaching the core building blocks of RAG, using the
same toy text/documents throughout: chunking -> embeddings -> build-your-own
embedding -> vector databases -> semantic/BM25/hybrid search + metadata filtering ->
cross-encoder reranking -> MMR -> document loading -> structured output -> LCEL RAG
chain -> conversation memory.

## Requirements

- **Python 3.14.4** (this is what was used to build/verify the notebook; anything
  3.11+ should work, but 3.14.4 is the exact verified version)
- A `.env` file at the **repo root** (three levels up from this folder) with:
  - `OPENAI_API_KEY` — used for OpenAI embeddings AND `gpt-4o-mini` chat/generation
    (structured output, LCEL RAG chain, capstone pipeline, conversation memory)
  - `QDRANT_URL` / `QDRANT_API_KEY` — used for the Qdrant Cloud vector store section
  (`sentence-transformers`, ChromaDB, and FAISS all run locally — no other keys
  needed)

## Setup from a fresh clone

`venv/` is intentionally **not** committed (it's gitignored) — recreate it locally:

```bash
cd teaching/rag_concepts
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
python3 -m ipykernel install --user --name rag_concepts_venv --display-name "Python (rag_concepts)"
```

Create `.env` at the repo root (see `.env.example` if present) with the three keys
listed above.

## How to run it

```bash
cd teaching/rag_concepts
source venv/bin/activate
jupyter notebook notebook.ipynb
```

In the Jupyter UI, make sure the kernel is set to **"Python (rag_concepts)"**
(Kernel -> Change Kernel) — running under a different Python environment will be
missing the packages installed above.

Or to re-run headless top to bottom (what verification used):

```bash
source venv/bin/activate
jupyter nbconvert --to notebook --execute --inplace notebook.ipynb \
  --ExecutePreprocessor.timeout=600 --ExecutePreprocessor.kernel_name=rag_concepts_venv
```

## Verified against

- **LLM/embeddings:** OpenAI `text-embedding-3-small` (real API calls) + local
  `sentence-transformers/all-MiniLM-L6-v2` (open-source, no key needed)
- **Vector stores:** ChromaDB (in-memory local), FAISS (`IndexFlatIP`, local), Qdrant
  Cloud (real managed cluster, collection `rag_concepts_toy_docs`)
- **Search:** BM25 (`rank_bm25`, local), semantic search + metadata filtering (Qdrant
  Cloud), hybrid search (reciprocal rank fusion, computed locally)
- **Reranking:** local HF cross-encoder `cross-encoder/ms-marco-MiniLM-L-6-v2`
- **Observability:** none (by design — this is a concept-mechanics notebook)

Verified 2026-07-18: executed top to bottom with no errors; every section's printed
output was inspected and confirmed meaningful (real embedding vectors, real
Qdrant Cloud search scores, BM25/hybrid/MMR all showing the expected qualitative
differences on the same toy query).

## Notes / fixes made during verification

- `qdrant-client` 1.18 dropped `.search()` in favor of `.query_points()` (returns
  `.points`) — both search calls in step f use the current API.
- Qdrant Cloud requires a payload index (`create_payload_index`) before filtering on
  a field — added right after collection creation in step e, used by the metadata
  filter in step f.

## Step i: Document loading (added 2026-07-18)

Adds a document-loading section covering LangChain's loader ecosystem:

- **Run for real:** `PyPDFLoader` (toy PDF), `TextLoader` (toy `.txt`), `WebBaseLoader`
  (a live Wikipedia page) — all verified against real files/network.
- **Shown as real code, not executed:** `SharePointLoader`, `S3FileLoader`/
  `S3DirectoryLoader`, `GCSFileLoader`/`GCSDirectoryLoader`, `GoogleDriveLoader` —
  guarded under `if False:` since this demo has no SharePoint/AWS/GCP credentials
  configured. Flip to `if True:` and supply real credentials to run them.

Re-verified 2026-07-18: full notebook re-executed top to bottom (all prior sections
plus the new step), zero errors, all outputs inspected.

## Steps j-m: Structured output, LCEL, RAG chain capstone, memory (added 2026-07-18)

- **Step j:** `ChatOpenAI.with_structured_output()` + a Pydantic model
  (`DocumentInsight`) extracts typed fields (topic, sentiment, entities) from a toy
  document — real `gpt-4o-mini` call, real validated Pydantic object returned.
- **Step k:** an LCEL chain (`RunnablePassthrough.assign | prompt | llm | parser`)
  wires step f's Qdrant semantic search into a real generated answer — the first
  point in the notebook where retrieval produces an actual RAG *answer*, not just
  search hits.
- **Step l (capstone):** `full_rag_pipeline()` chains semantic search -> MMR
  (step h) -> cross-encoder reranking (step g) -> LCEL generation into one real,
  runnable RAG pipeline, reusing every earlier building block.
- **Step m:** `RunnableWithMessageHistory` wraps a conversational chain with
  per-session memory; a two-turn toy conversation shows a follow-up question
  ("What is the biggest threat to it?") correctly resolved using memory of turn 1.
  Note: this prints a real `LangChainDeprecationWarning` — LangChain now points
  newer projects toward LangGraph's built-in persistence, called out explicitly in
  the notebook's markdown.

**Real bug fixed during verification:** the first version of steps k/l's prompt was
too strict ("answer using ONLY the context... say so if it doesn't contain the
answer") and both the LCEL chain and the capstone pipeline replied "the context does
not contain the answer" even though the retrieved context was clearly relevant —
just not phrased as a direct answer. Reworded the prompt to ask the model to
synthesize an answer from related/causal context, confirmed with a real re-run that
both chains now produce a substantive, correct answer.

Re-verified 2026-07-18: full notebook (13 sections, 45 cells) re-executed top to
bottom, zero errors, all outputs inspected including the corrected RAG answers and
the two-turn memory conversation.
