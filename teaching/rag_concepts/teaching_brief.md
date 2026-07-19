# Teaching Brief: RAG Concepts (Chunking → Embeddings → Vector DBs → Search → Reranking → MMR)

## Description (as given by user)
A single progressive notebook using toy text/docs throughout to teach, in order:

- Chunking: what it is (markdown), the different kinds LangChain supports
  (recursive, fixed-length, semantic, and others), code applying each kind
  to the same sample text and showing how output differs, pros/cons.
- Embeddings: what they are (markdown), paid vs open-source (HF) models
  available, code creating embedding functions for OpenAI and an
  open-source model, showing the same sample word/text embedded by each
  and printing the vectors + their lengths, pros/cons, then a step-by-step
  explanation of building your own embedding model and actually building
  a tiny "baby embedding" model.
- Vector databases: what they are (markdown), ChromaDB / FAISS / Qdrant /
  Pinecone / Weaviate / AWS / Azure / GCP vector DBs and their differences/
  pros/cons, code converting sample text to embeddings and pushing to
  ChromaDB, FAISS, and Qdrant Cloud specifically (all three get real code).
- Search: what semantic search is, what BM25 is, what hybrid search is
  (markdown), using the data already pushed to Qdrant to show each search
  type behaving differently in code, including metadata filtering.
- Cross-encoder reranking: what it is (markdown) and code demonstrating it.
- MMR (Maximal Marginal Relevance): explained and demonstrated in code.

Idea: use toy text/doc/examples throughout so every concept is concretely
visible in printed output, not just described.

## Steps (in order, each builds on the previous)
a) Chunking concepts + LangChain splitter types + code comparison + pros/cons
b) Embeddings concepts + OpenAI + open-source (HF) embedding functions + comparison + pros/cons
c) Build-your-own-embedding walkthrough (markdown) + tiny "baby embedding" implementation
d) Vector database concepts (Chroma/FAISS/Qdrant/Pinecone/Weaviate/cloud-managed) + pros/cons
e) Push toy embeddings to ChromaDB, FAISS, and Qdrant Cloud
f) Semantic search vs BM25 vs hybrid search, demonstrated against the Qdrant data, incl. metadata filtering
g) Cross-encoder reranking (markdown + code)
h) MMR (markdown + code)
i) Document loading with LangChain (PDF, plain text, web URL run for real; SharePoint, AWS S3, GCS/Google Drive shown as real code but not executed, no cloud credentials configured) — added 2026-07-18
j) Output parsers, structured output, Pydantic-based extraction (theory + real gpt-4o-mini structured extraction) — added 2026-07-18
k) LCEL chains: retrieve -> prompt -> generate, wiring step f's Qdrant retrieval into a real gpt-4o-mini call — added 2026-07-18
l) Capstone: minimal end-to-end RAG chain (semantic search -> MMR -> cross-encoder rerank -> generate), reusing every retrieval building block from steps b/f/g/h — added 2026-07-18
m) Memory / conversation history via RunnableWithMessageHistory (modern approach), legacy ConversationBufferMemory mentioned in markdown only — added 2026-07-18

## Format
notebook

## Happy-path test case (user-approved)
A student opens the notebook and runs it top to bottom. In each section
they see: a markdown explanation of the concept, runnable code applied to
the same toy paragraph/text used throughout, printed output showing the
concrete result (chunk boundaries, vector snippets + lengths, search hits
with scores, reranked order, MMR-selected results), and a pros/cons
markdown summary. By the end, they've pushed the same toy text into
ChromaDB, FAISS, and Qdrant Cloud, and can see semantic search, BM25,
hybrid search, cross-encoder reranking, and MMR all run against that same
data, side by side.

## Observability
none

## Vector store
chromadb + faiss + qdrant (all three, explicitly)

## Constraints
- OPENAI_API_KEY required (OpenAI embeddings) — verified via a real
  embeddings API call (text-embedding-3-small, 1536 dims).
- QDRANT_URL / QDRANT_API_KEY required (Qdrant Cloud) — verified via a
  real `get_collections()` call.
- Open-source embedding model runs locally via sentence-transformers
  (e.g. all-MiniLM-L6-v2) — no key required.
- Cross-encoder reranking uses a local HF cross-encoder model — no key
  required.
- BM25 via a local library (e.g. rank_bm25) — no key required.
- No mock mode anywhere — all provider calls are real.
- Chat/generation (steps j, k, l, m) uses OpenAI `gpt-4o-mini` via `ChatOpenAI` —
  same `OPENAI_API_KEY`, verified with a real chat completion call.

## Audience level
beginner

## Decisions
- Embedding providers: OpenAI (paid) + one open-source HF model, per user
  choice — not open-source-only or OpenAI-only.
- All three vector stores (ChromaDB, FAISS, Qdrant Cloud) get real working
  code, not just one representative store.
- No Phoenix observability — this is a concept-mechanics notebook, not a
  production-quality RAG demo.

## Steps (retrieval_techniques.ipynb — separate companion notebook, added 2026-07-19)

A second, standalone notebook focused entirely on retrieval techniques,
with its own dummy knowledge base (`data/retrieval_kb.py`: a fictional
drone company "Aurora Robotics" — a long structured handbook for
parent-child/neighbor-expansion, ~20 short KB passages with metadata
(incl. 2 intentional near-duplicates) for search/filter/rerank/dedup/MMR/
query-transformation techniques, and a SQL product catalog for SQL
retrieval). Every technique section: markdown (what it is / when best
used / popularity / pros-cons / advanced-RAG-stack verdict) + runnable
code against the Aurora data.

- 17 essential techniques (all fully implemented, real calls, no mocks):
  dense semantic retrieval, sparse BM25, hybrid retrieval, metadata
  filtering, parent-child retrieval, neighbor expansion, Reciprocal Rank
  Fusion, cross-encoder reranking, deduplication, MMR, query rewriting,
  multi-query retrieval, query decomposition, relevance grading,
  iterative retrieval, SQL retrieval (SQLite, text-to-SQL via
  gpt-4o-mini), web fallback (real Tavily API call).
- 9 experimental techniques (markdown + lighter runnable code example
  each): HyDE, semantic chunking, multi-vector retrieval,
  hypothetical-question indexing, contextualized chunks, knowledge-graph
  retrieval, GraphRAG, LLM reranking, contextual compression.
- Closing section: recommended end-to-end retrieval pipeline (ASCII
  diagram) + a final combined example (query rewriting -> routing ->
  hybrid retrieval -> RRF -> dedup -> cross-encoder rerank -> relevance
  grading -> SQL retrieval -> generation) + a revision-summary table.

Uses `OPENAI_API_KEY` (embeddings + gpt-4o-mini) and `TAVILY_API_KEY`
(real web search for the web-fallback section), both verified via real
calls. Local-only: `rank_bm25`, `sentence-transformers` cross-encoder,
in-memory ChromaDB, in-memory SQLite.

Verified 2026-07-19: full notebook (58 cells) executed top to bottom via
`nbconvert --execute`, zero errors. Real bug found and fixed during
verification: the final pipeline's generation prompt originally passed
raw SQL tuples (`[(42,)]`), which the LLM misread as "1 unit"; fixed by
labeling SQL rows with column names before the generation call.

## Checkpoint status
- Description: approved
- Clarifications: approved
- Format: approved
- Happy-path test case: approved
- API key verification: verified (OpenAI + Qdrant Cloud, real calls succeeded)
- Observability: approved
- Vector store: approved
- Ready to generate: approved
- Build: complete
- Verify: complete
