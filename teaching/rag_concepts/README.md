# RAG Concepts

Two companion Jupyter notebooks:

- **`notebook.ipynb`** — the core building blocks of RAG, using the same toy
  text/documents throughout: chunking -> embeddings -> build-your-own embedding ->
  vector databases -> semantic/BM25/hybrid search + metadata filtering ->
  cross-encoder reranking -> MMR -> document loading -> structured output -> LCEL
  RAG chain -> conversation memory.
- **`retrieval_techniques.ipynb`** — a deep dive on retrieval specifically: 17
  essential techniques (dense, BM25, hybrid, metadata filtering, parent-child,
  neighbor expansion, RRF, cross-encoder reranking, dedup, MMR, query rewriting,
  multi-query, query decomposition, relevance grading, iterative retrieval, SQL
  retrieval, web fallback) plus 9 experimental techniques (HyDE, semantic
  chunking, multi-vector, hypothetical-question indexing, contextualized chunks,
  knowledge-graph retrieval, GraphRAG, LLM reranking, contextual compression),
  ending with a recommended end-to-end retrieval pipeline. Uses its own dummy
  knowledge base (`data/retrieval_kb.py`) — a fictional drone company, Aurora
  Robotics, with a long structured handbook, ~20 short FAQ/spec passages
  (including 2 intentional near-duplicates), and a small SQL product catalog.

## Requirements

- **Python 3.14.4** (this is what was used to build/verify the notebook; anything
  3.11+ should work, but 3.14.4 is the exact verified version)
- A `.env` file at the **repo root** (three levels up from this folder) with:
  - `OPENAI_API_KEY` — used for OpenAI embeddings AND `gpt-4o-mini` chat/generation
    (structured output, LCEL RAG chain, capstone pipeline, conversation memory)
  - `QDRANT_URL` / `QDRANT_API_KEY` — used for the Qdrant Cloud vector store section
  - `TAVILY_API_KEY` — used by `retrieval_techniques.ipynb`'s web-fallback section
    for a real live web search call
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
jupyter notebook notebook.ipynb              # core RAG building blocks
jupyter notebook retrieval_techniques.ipynb  # retrieval-technique deep dive
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

## New notebook: `retrieval_techniques.ipynb` (added 2026-07-19)

A separate, standalone notebook (58 cells) focused entirely on retrieval, built
against its own dummy knowledge base in `data/retrieval_kb.py` (a fictional
drone company, "Aurora Robotics", with a long structured handbook, ~20 short
FAQ/spec passages with metadata, two intentional near-duplicates, and a small
SQL product catalog). Every technique section follows the same pattern: a
markdown block (what it is / when best used / popularity / pros-cons / whether
it belongs in an advanced-RAG stack) followed by runnable code against the
Aurora data with printed output.

- 17 essential techniques, each fully implemented: dense semantic retrieval,
  sparse BM25, hybrid retrieval, metadata filtering, parent-child retrieval,
  neighbor expansion, Reciprocal Rank Fusion, cross-encoder reranking,
  deduplication, MMR, query rewriting, multi-query retrieval, query
  decomposition, relevance grading, iterative retrieval, SQL retrieval
  (text-to-SQL against an in-memory SQLite table), and web fallback (a real
  Tavily API call).
- 9 experimental techniques, each with a markdown explanation plus a runnable
  (if lighter-weight) code example: HyDE, semantic chunking, multi-vector
  retrieval, hypothetical-question indexing, contextualized chunks,
  knowledge-graph retrieval, GraphRAG, LLM reranking, contextual compression.
- Closing section: a recommended end-to-end retrieval pipeline (ASCII diagram)
  plus a final example that runs query rewriting -> routing -> hybrid
  retrieval -> RRF -> dedup -> cross-encoder rerank -> relevance grading ->
  SQL retrieval -> generation on one genuinely compound question, plus a
  revision-summary table of every technique.

**Real bug found and fixed during verification:** the final combined-pipeline
example originally passed raw SQL rows as `[(42,)]` into the generation
prompt; the LLM misread the tuple and answered "1 unit in stock" instead of
42. Fixed by labeling SQL results with column names (`[{'stock_units': 42}]`)
before handing them to the LLM — re-verified the corrected answer.

Verified 2026-07-19: executed top to bottom via `nbconvert --execute`, zero
errors across all 58 cells; spot-checked SQL retrieval, web fallback (real
Tavily results), and the final combined pipeline's output for correctness.

Run it the same way as the other notebook:

```bash
source venv/bin/activate
jupyter nbconvert --to notebook --execute --inplace retrieval_techniques.ipynb \
  --ExecutePreprocessor.timeout=600 --ExecutePreprocessor.kernel_name=rag_concepts_venv
```
