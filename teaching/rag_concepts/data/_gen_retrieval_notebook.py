"""One-off generator for retrieval_techniques.ipynb. Run once, then delete
or keep for future regeneration. Produces the notebook via nbformat so the
large cell-by-cell content is easy to maintain as plain Python strings.
"""
import nbformat as nbf

nb = nbf.v4.new_notebook()
cells = []


def md(src):
    cells.append(nbf.v4.new_markdown_cell(src.strip("\n")))


def code(src):
    cells.append(nbf.v4.new_code_cell(src.strip("\n")))


# ===========================================================================
# Intro
# ===========================================================================
md("""
# RAG Retrieval Techniques, End to End

This notebook is a companion to `notebook.ipynb` and focuses **only on
retrieval** — the many ways to go from "a user question" to "the right
chunks of context" before an LLM ever generates an answer.

**Scenario used throughout:** Aurora Robotics, a fictional consumer-drone
company. Its knowledge base (`data/retrieval_kb.py`) intentionally has
three different shapes of data, because different retrieval techniques
exist to handle different shapes:

1. A long, structured **handbook document** (warranty + returns policy),
   broken into sections and paragraphs -> used for parent-child retrieval
   and neighbor expansion.
2. Twenty short, independent **KB passages** (FAQs, specs, policies) with
   metadata (`topic`, `doc_type`, `department`, `date`) and two
   intentional near-duplicates -> used for search, filtering, reranking,
   dedup, MMR, and the query-transformation techniques.
3. A small structured **product catalog** loaded into SQLite -> used for
   SQL retrieval.

Every section below follows the same pattern:
- **What it is / when it's best used / how popular it is / pros & cons /
  should it be in your advanced-RAG stack** (markdown)
- **Runnable code** against the Aurora Robotics data, with printed output
  so you can see exactly how the technique behaves and how it differs
  from the others.

**Sections:**

Essential (implemented in full): dense semantic retrieval, sparse BM25,
hybrid retrieval, metadata filtering, parent-child retrieval, neighbor
expansion, Reciprocal Rank Fusion, cross-encoder reranking,
deduplication, MMR, query rewriting, multi-query retrieval, query
decomposition, relevance grading, iterative retrieval, SQL retrieval,
web fallback.

Experimental (lighter treatment, still runnable): HyDE, semantic
chunking, multi-vector retrieval, hypothetical-question indexing,
contextualized chunks, knowledge-graph retrieval, GraphRAG, LLM
reranking, contextual compression.

Final section: putting it all together into one recommended pipeline.
""")

# ===========================================================================
# Setup
# ===========================================================================
code("""
# ---- Setup: env, imports, shared toy knowledge base, embeddings, Chroma ----
import os
import sys
import json
import sqlite3

REPO_ROOT = os.path.abspath(os.path.join(os.getcwd(), "..", ".."))
sys.path.insert(0, os.path.join(os.getcwd(), "data"))

from dotenv import load_dotenv
load_dotenv(os.path.join(REPO_ROOT, ".env"))

assert os.environ.get("OPENAI_API_KEY"), "OPENAI_API_KEY not found - check your .env"

from retrieval_kb import HANDBOOK_SECTIONS, KB_DOCUMENTS, PRODUCT_CATALOG, QUERIES

import chromadb
from langchain_openai import OpenAIEmbeddings, ChatOpenAI

embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

# In-memory Chroma collection holding the 20 short KB passages (kb_001..kb_020)
chroma_client = chromadb.EphemeralClient()
kb_collection = chroma_client.get_or_create_collection("aurora_kb")

kb_texts = [d["text"] for d in KB_DOCUMENTS]
kb_ids = [d["id"] for d in KB_DOCUMENTS]
kb_metadatas = [d["metadata"] for d in KB_DOCUMENTS]
kb_vectors = embeddings.embed_documents(kb_texts)

kb_collection.add(ids=kb_ids, embeddings=kb_vectors, documents=kb_texts, metadatas=kb_metadatas)
print(f"Loaded {kb_collection.count()} KB passages into an in-memory Chroma collection.")
print("Example passage:", KB_DOCUMENTS[0]["text"])
""")

# ===========================================================================
# 1. Dense semantic retrieval
# ===========================================================================
md("""
## 1. Dense semantic retrieval

**What it is:** Embed the query and every document into the same vector
space, then rank documents by vector similarity (cosine/dot product).
"Dense" refers to the embedding vectors — every dimension carries some
signal, unlike sparse keyword vectors.

**When it's best used:** The default retrieval method for almost any
modern RAG system. Excellent when the user's wording differs from the
document's wording ("battery care" vs. "storage charge level") because it
matches on *meaning*, not exact tokens.

**Popularity:** Extremely high — this is the baseline every production RAG
system starts with.

**Pros:** Understands paraphrasing and synonyms; language-agnostic to a
degree; single embedding call per query.
**Cons:** Can miss exact identifiers (SKUs, error codes, version numbers)
that keyword search nails; embedding cost/latency; needs a vector index.

**Should it be in your advanced-RAG stack?** Yes — it is the foundation,
almost always paired with something else (see hybrid retrieval below).
""")

code("""
# ---- Dense semantic retrieval against the Aurora KB ----
query = QUERIES["dense"]
query_vec = embeddings.embed_query(query)

dense_hits = kb_collection.query(query_embeddings=[query_vec], n_results=3)

print(f"Query: {query!r}\\n")
for doc, dist, meta in zip(dense_hits["documents"][0], dense_hits["distances"][0], dense_hits["metadatas"][0]):
    print(f"[dist={dist:.4f}] ({meta['topic']}) {doc}")
""")

# ===========================================================================
# 2. Sparse BM25 retrieval
# ===========================================================================
md("""
## 2. Sparse BM25 retrieval

**What it is:** A classic keyword-ranking algorithm (an improvement on
TF-IDF). It scores documents by how often query *terms* literally appear,
weighted by term rarity across the corpus and document length. No
embeddings, no neural network.

**When it's best used:** Exact-match-sensitive queries — product codes,
firmware versions, error messages, names, numbers — anything where the
literal token matters more than the meaning.

**Popularity:** Very high as a component of hybrid search; rare as a
standalone retriever in modern systems, but still the backbone of most
search engines historically (Elasticsearch, Lucene).

**Pros:** No embedding cost, fast, deterministic, excellent on exact
terms/identifiers, easy to explain.
**Cons:** No understanding of synonyms or paraphrasing at all — "battery
care" will not match "storage charge level".

**Should it be in your advanced-RAG stack?** Yes, in combination with
dense retrieval (see hybrid below) — rarely as the only method.
""")

code("""
# ---- Sparse BM25 retrieval against the same Aurora KB ----
from rank_bm25 import BM25Okapi

def tokenize(text):
    return text.lower().replace(".", "").replace(",", "").split()

bm25_corpus_tokens = [tokenize(t) for t in kb_texts]
bm25 = BM25Okapi(bm25_corpus_tokens)

query = QUERIES["sparse_bm25"]
bm25_scores = bm25.get_scores(tokenize(query))
bm25_ranked = sorted(zip(kb_ids, kb_texts, bm25_scores), key=lambda x: x[2], reverse=True)[:3]

print(f"Query: {query!r}\\n")
for doc_id, text, score in bm25_ranked:
    print(f"[bm25={score:.3f}] ({doc_id}) {text}")

print("\\nContrast: the same query run through dense retrieval only -")
dense_only = kb_collection.query(query_embeddings=[embeddings.embed_query(query)], n_results=3)
for doc, dist in zip(dense_only["documents"][0], dense_only["distances"][0]):
    print(f"[dist={dist:.4f}] {doc}")
print("\\nBM25 nails the exact 'firmware version 3.2' / 'GPS drift' wording; dense retrieval "
      "ranks by general topical similarity and can rank a different passage first.")
""")

# ===========================================================================
# 3. Hybrid retrieval
# ===========================================================================
md("""
## 3. Hybrid retrieval

**What it is:** Run dense and sparse (BM25) retrieval in parallel over the
same query, then combine their result lists into one ranking — usually by
weighted score fusion or Reciprocal Rank Fusion (RRF, covered in its own
section below).

**When it's best used:** Production RAG systems that need to handle both
"fuzzy" natural-language questions and exact-identifier lookups well,
which is most real-world knowledge bases.

**Popularity:** The de facto standard in modern production RAG (Qdrant,
Weaviate, Elasticsearch, and Azure AI Search all ship hybrid search as a
first-class feature).

**Pros:** Gets both semantic recall and exact-match precision; robust to
query style (natural language or keyword-y).
**Cons:** More moving parts (two retrieval systems); needs a fusion
strategy and tuning of the weighting between the two.

**Should it be in your advanced-RAG stack?** Yes — for most real
production systems, hybrid is the recommended default over dense-only.
""")

code("""
# ---- Hybrid retrieval: weighted combination of dense + BM25 scores ----
query = QUERIES["hybrid"]

# Dense scores (convert distance to a similarity-like score: smaller distance = higher score)
dense_result = kb_collection.query(query_embeddings=[embeddings.embed_query(query)], n_results=len(kb_ids))
dense_score_by_id = {}
for doc_id, dist in zip(dense_result["ids"][0], dense_result["distances"][0]):
    dense_score_by_id[doc_id] = 1.0 / (1.0 + dist)

# BM25 scores, normalized to 0-1
bm25_raw = bm25.get_scores(tokenize(query))
max_bm25 = max(bm25_raw) or 1.0
bm25_score_by_id = {doc_id: score / max_bm25 for doc_id, score in zip(kb_ids, bm25_raw)}

alpha = 0.5  # weight between dense (alpha) and BM25 (1 - alpha)
hybrid_scores = {
    doc_id: alpha * dense_score_by_id.get(doc_id, 0) + (1 - alpha) * bm25_score_by_id.get(doc_id, 0)
    for doc_id in kb_ids
}
hybrid_ranked = sorted(hybrid_scores.items(), key=lambda x: x[1], reverse=True)[:3]

text_by_id = dict(zip(kb_ids, kb_texts))
print(f"Query: {query!r}\\n")
for doc_id, score in hybrid_ranked:
    print(f"[hybrid={score:.3f} dense={dense_score_by_id[doc_id]:.3f} bm25={bm25_score_by_id[doc_id]:.3f}] "
          f"({doc_id}) {text_by_id[doc_id]}")
""")

# ===========================================================================
# 4. Metadata filtering
# ===========================================================================
md("""
## 4. Metadata filtering

**What it is:** Restrict retrieval to documents whose metadata matches a
condition (e.g. `department == "support"`, `date >= "2026-01-01"`) *before
or during* the vector search, instead of relying on semantic similarity
alone to rank the right documents to the top.

**When it's best used:** Multi-tenant data, permission scoping ("only
this user's documents"), freshness requirements ("only this year's
docs"), or narrowing a broad KB to the right subset (e.g. only
`doc_type == "policy"` for a compliance question).

**Popularity:** Very high in production — nearly every vector DB (Chroma,
Qdrant, Pinecone, Weaviate) supports filtered search natively.

**Pros:** Precise, cheap (no extra model calls), prevents irrelevant
departments/topics from ever competing for the top-k slots.
**Cons:** Requires metadata to be captured accurately at ingestion time;
overly strict filters can filter out the correct answer if metadata is
wrong or the filter is mis-specified.

**Should it be in your advanced-RAG stack?** Yes, whenever your documents
have natural boundaries (tenant, department, doc type, date) worth
enforcing.
""")

code("""
# ---- Metadata filtering: same query, unfiltered vs. filtered to doc_type=policy ----
query = QUERIES["metadata_filter"]
query_vec = embeddings.embed_query(query)

unfiltered = kb_collection.query(query_embeddings=[query_vec], n_results=3)
filtered = kb_collection.query(
    query_embeddings=[query_vec],
    n_results=3,
    where={"doc_type": "policy"},
)

print(f"Query: {query!r}\\n")
print("-- Unfiltered top 3 --")
for doc, meta in zip(unfiltered["documents"][0], unfiltered["metadatas"][0]):
    print(f"({meta['doc_type']}/{meta['department']}) {doc}")

print("\\n-- Filtered to doc_type == 'policy' --")
for doc, meta in zip(filtered["documents"][0], filtered["metadatas"][0]):
    print(f"({meta['doc_type']}/{meta['department']}) {doc}")
""")

# ===========================================================================
# 5. Parent-child retrieval
# ===========================================================================
md("""
## 5. Parent-child retrieval

**What it is:** Index small child chunks (e.g. single paragraphs) for
precise vector matching, but when a child chunk is retrieved, return (or
also feed the LLM) its larger parent context (e.g. the whole section) —
so search precision comes from small chunks while generation quality
comes from full context.

**When it's best used:** Long structured documents (handbooks, contracts,
manuals) where a question might match one paragraph precisely, but a good
answer needs the surrounding section for full context.

**Popularity:** High in mature RAG systems (LangChain's
`ParentDocumentRetriever` is a direct implementation of this pattern);
less common in simple/naive RAG demos.

**Pros:** Best of both worlds — precise matching + complete context;
avoids the "chunk too small to answer, chunk too big to match" tradeoff.
**Cons:** More indexing complexity (two levels of storage); parent
context can add a lot of tokens to the LLM call.

**Should it be in your advanced-RAG stack?** Yes, whenever your source
documents have real hierarchical structure with sections you can be
returning as a unit.
""")

code("""
# ---- Parent-child retrieval over the Aurora warranty handbook ----
# Index every paragraph (child) but remember which section (parent) it belongs to.
child_texts, child_ids, child_to_parent = [], [], {}
for section in HANDBOOK_SECTIONS:
    for i, para in enumerate(section["paragraphs"]):
        child_id = f"{section['section_id']}_p{i}"
        child_texts.append(para)
        child_ids.append(child_id)
        child_to_parent[child_id] = section

child_vectors = embeddings.embed_documents(child_texts)
child_collection = chroma_client.get_or_create_collection("aurora_handbook_children")
child_collection.add(ids=child_ids, embeddings=child_vectors, documents=child_texts)

query = QUERIES["parent_child"]
result = child_collection.query(query_embeddings=[embeddings.embed_query(query)], n_results=1)
best_child_id = result["ids"][0][0]
best_child_text = result["documents"][0][0]
parent_section = child_to_parent[best_child_id]

print(f"Query: {query!r}\\n")
print(f"-- Matched CHILD paragraph ({best_child_id}) --")
print(best_child_text)
print(f"\\n-- Returned PARENT context instead: full section '{parent_section['heading']}' --")
for para in parent_section["paragraphs"]:
    print("-", para)
print("\\nNotice: the matched child paragraph alone only describes claim review timing. "
      "The full parent section also includes filing and shipping-back steps needed to fully "
      "answer 'walk me through the entire process'.")
""")

# ===========================================================================
# 6. Neighbor expansion
# ===========================================================================
md("""
## 6. Neighbor expansion

**What it is:** When a chunk is retrieved, also pull in its immediate
neighbors (the chunk right before and/or after it in the original
document order) and include them in the context sent to the LLM — even
though only the middle chunk matched the query.

**When it's best used:** Sequential/narrative documents where an answer
often spills across adjacent chunk boundaries (e.g. "what happens after
X" naturally continues into the next paragraph).

**Popularity:** Moderate-to-high; a lightweight, simple technique often
used as a cheaper alternative to full parent-child indexing.

**Pros:** Very cheap to implement (just chunk-index arithmetic); no
second index needed; fixes "answer got cut off at the chunk boundary".
**Cons:** Blunt — always adds neighbors regardless of whether they're
actually relevant, which can dilute context with padding.

**Should it be in your advanced-RAG stack?** Optional — a good cheap win
for sequential documents, but parent-child retrieval is a more precise
solution if you can afford the extra indexing.
""")

code("""
# ---- Neighbor expansion over the same handbook paragraphs ----
# child_ids is already in original document order: sec1_p0, sec1_p1, sec1_p2, sec2_p0, ...
query = QUERIES["neighbor_expansion"]
result = child_collection.query(query_embeddings=[embeddings.embed_query(query)], n_results=1)
matched_id = result["ids"][0][0]
matched_index = child_ids.index(matched_id)

print(f"Query: {query!r}\\n")
print(f"-- Matched chunk only ({matched_id}) --")
print(child_texts[matched_index])

start = max(0, matched_index - 1)
end = min(len(child_ids), matched_index + 2)
print(f"\\n-- Matched chunk + neighbors ({child_ids[start:end]}) --")
for i in range(start, end):
    marker = ">> " if i == matched_index else "   "
    print(f"{marker}{child_texts[i]}")
print("\\nThe matched chunk alone only says the claim was approved and a label was sent. "
      "The neighbor after it (returned via expansion) reveals the actual repair timeline.")
""")

# ===========================================================================
# 7. Reciprocal Rank Fusion
# ===========================================================================
md("""
## 7. Reciprocal Rank Fusion (RRF)

**What it is:** A rank-based (not score-based) way to fuse multiple
ranked result lists (e.g. dense results + BM25 results) into one. Each
document gets `1 / (k + rank)` points from each list it appears in
(rank starting at 1, `k` a small constant like 60), and the fused score
is the sum across lists.

**When it's best used:** Combining retrieval lists whose raw scores are
on incompatible scales (cosine distance vs. BM25 score) — RRF sidesteps
score normalization entirely by only looking at rank position.

**Popularity:** Very high — it's the standard fusion method in hybrid
search implementations (Elasticsearch, Azure AI Search, Qdrant all offer
RRF), preferred over manual score-weighting like in the hybrid section
above.

**Pros:** No score normalization needed; simple and robust; works with
any number of ranked lists (not just two).
**Cons:** Ignores the *magnitude* of how much better a top result is
(rank 1 vs rank 2 always gets the same fixed gap); the constant `k` is a
tuning knob.

**Should it be in your advanced-RAG stack?** Yes — prefer RRF over manual
score-weighting for fusing dense+sparse (or multi-query) result lists.
""")

code("""
# ---- RRF: fuse the dense ranking and the BM25 ranking for the same query ----
def rrf_fuse(ranked_lists, k=60):
    scores = {}
    for ranked_ids in ranked_lists:
        for rank, doc_id in enumerate(ranked_ids, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)

query = QUERIES["rrf"]
dense_ranked_ids = kb_collection.query(query_embeddings=[embeddings.embed_query(query)], n_results=len(kb_ids))["ids"][0]
bm25_ranked_ids = [doc_id for doc_id, _ in sorted(zip(kb_ids, bm25.get_scores(tokenize(query))), key=lambda x: x[1], reverse=True)]

fused = rrf_fuse([dense_ranked_ids, bm25_ranked_ids])[:3]

print(f"Query: {query!r}\\n")
print("Dense top 3:", dense_ranked_ids[:3])
print("BM25 top 3: ", bm25_ranked_ids[:3])
print("\\nRRF-fused top 3:")
for doc_id, score in fused:
    print(f"[rrf={score:.4f}] ({doc_id}) {text_by_id[doc_id]}")
""")

# ===========================================================================
# 8. Cross-encoder reranking
# ===========================================================================
md("""
## 8. Cross-encoder reranking

**What it is:** After an initial retriever (dense/sparse/hybrid) returns a
candidate list, run a *cross-encoder* model that takes the (query,
document) pair **together** as input and outputs a direct relevance
score — instead of comparing two separately-computed vectors (a
"bi-encoder", which is what dense retrieval uses).

**When it's best used:** As a second-pass refinement over a top-k
candidate list (e.g. top 20-50), never as the first-pass retriever over
an entire corpus — cross-encoders are too slow to run against every
document.

**Popularity:** Very high in production RAG — reranking is one of the
single highest-ROI additions to a naive RAG pipeline.

**Pros:** Much higher relevance precision than bi-encoder similarity
alone, because the model sees the query and document jointly.
**Cons:** Slower (one forward pass per candidate pair); cannot be
precomputed/indexed like embeddings; adds latency to the request path.

**Should it be in your advanced-RAG stack?** Yes — one of the most
worthwhile additions to any RAG system with more than trivial recall
noise in first-pass retrieval.
""")

code("""
# ---- Cross-encoder reranking of the dense candidates ----
from sentence_transformers import CrossEncoder

reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

query = QUERIES["cross_encoder_rerank"]
candidates = kb_collection.query(query_embeddings=[embeddings.embed_query(query)], n_results=5)
candidate_ids = candidates["ids"][0]
candidate_texts = candidates["documents"][0]

print(f"Query: {query!r}\\n")
print("-- Bi-encoder (dense) order --")
for doc_id, text in zip(candidate_ids, candidate_texts):
    print(f"({doc_id}) {text}")

pairs = [(query, text) for text in candidate_texts]
rerank_scores = reranker.predict(pairs)
reranked = sorted(zip(candidate_ids, candidate_texts, rerank_scores), key=lambda x: x[2], reverse=True)

print("\\n-- Cross-encoder reranked order --")
for doc_id, text, score in reranked:
    print(f"[score={score:.3f}] ({doc_id}) {text}")
print("\\nThe cross-encoder often promotes the passage that most directly answers the question "
      "even if it wasn't the closest by raw embedding distance.")
""")

# ===========================================================================
# 9. Deduplication
# ===========================================================================
md("""
## 9. Deduplication

**What it is:** Detect and remove near-duplicate passages from a
retrieved set before sending them to the LLM — e.g. two FAQ entries that
restate the same fact in different words. Usually done via embedding
similarity above a high threshold (not just exact string match).

**When it's best used:** Any KB that has been built up over time from
multiple sources (support tickets, docs, wikis) where the same fact gets
restated more than once — extremely common in practice.

**Popularity:** Moderate-to-high in mature pipelines; frequently skipped
in naive RAG demos, which is why context windows get wasted on
repeated information.

**Pros:** Saves context-window budget for genuinely distinct information;
reduces the LLM being biased by seeing the same fact twice ("majority
vote" effect); cheap (just cosine similarity across the shortlist).
**Cons:** Needs a similarity threshold to tune (too low = merges genuinely
different facts, too high = duplicates slip through); adds a pass over
the candidate set.

**Should it be in your advanced-RAG stack?** Yes, if your source corpus
has any redundancy at all — nearly free to add.
""")

code("""
# ---- Deduplication: kb_003 and kb_017 both restate the return window ----
import numpy as np

def cosine_sim(a, b):
    a, b = np.array(a), np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

query = QUERIES["dedup"]
candidates = kb_collection.query(query_embeddings=[embeddings.embed_query(query)], n_results=5)
candidate_ids = candidates["ids"][0]
candidate_texts = candidates["documents"][0]
candidate_vecs = embeddings.embed_documents(candidate_texts)

print(f"Query: {query!r}\\n")
print("-- Raw candidates (before dedup) --")
for doc_id, text in zip(candidate_ids, candidate_texts):
    print(f"({doc_id}) {text}")

threshold = 0.93
kept_ids, kept_texts, kept_vecs = [], [], []
for doc_id, text, vec in zip(candidate_ids, candidate_texts, candidate_vecs):
    is_dup = any(cosine_sim(vec, kv) >= threshold for kv in kept_vecs)
    if is_dup:
        print(f"\\nDropping ({doc_id}) as a near-duplicate of an already-kept passage.")
        continue
    kept_ids.append(doc_id); kept_texts.append(text); kept_vecs.append(vec)

print("\\n-- After dedup --")
for doc_id, text in zip(kept_ids, kept_texts):
    print(f"({doc_id}) {text}")
""")

# ===========================================================================
# 10. MMR
# ===========================================================================
md("""
## 10. Maximal Marginal Relevance (MMR)

**What it is:** A selection algorithm that iteratively picks the next
document maximizing `lambda * relevance_to_query - (1 - lambda) *
max_similarity_to_already_selected`. It trades off pure relevance against
diversity, so the final set doesn't consist of 5 near-identical passages.

**When it's best used:** Broad/exploratory queries where you want
*coverage* across different facets of the answer, not just the single
most relevant fact repeated with slight variation (dedup removes exact
near-duplicates; MMR goes further and actively diversifies topic
coverage among genuinely distinct-but-similar documents).

**Popularity:** High — a standard option in most vector-DB SDKs and
LangChain retrievers (`search_type="mmr"`).

**Pros:** Better topical coverage in the final context; reduces
redundancy even among documents that aren't literal near-duplicates.
**Cons:** The `lambda` diversity/relevance tradeoff needs tuning; can
demote a highly-relevant document in favor of diversity when you
actually wanted the single best answer.

**Should it be in your advanced-RAG stack?** Situational — valuable for
broad/summarization-style queries, less useful for narrow factual
questions where you want the single best passage, not a diverse set.
""")

code("""
# ---- MMR over a broad query where topical diversity matters ----
def mmr(query_vec, candidate_ids, candidate_vecs, candidate_texts, k=3, lambda_param=0.6):
    selected = []
    remaining = list(range(len(candidate_ids)))
    while remaining and len(selected) < k:
        best_idx, best_score = None, -1e9
        for i in remaining:
            relevance = cosine_sim(query_vec, candidate_vecs[i])
            diversity_penalty = max([cosine_sim(candidate_vecs[i], candidate_vecs[j]) for j in selected], default=0.0)
            mmr_score = lambda_param * relevance - (1 - lambda_param) * diversity_penalty
            if mmr_score > best_score:
                best_score, best_idx = mmr_score, i
        selected.append(best_idx)
        remaining.remove(best_idx)
    return selected

query = QUERIES["mmr"]
query_vec = embeddings.embed_query(query)
candidates = kb_collection.query(query_embeddings=[query_vec], n_results=8)
candidate_ids = candidates["ids"][0]
candidate_texts = candidates["documents"][0]
candidate_vecs = embeddings.embed_documents(candidate_texts)

print(f"Query: {query!r}\\n")
print("-- Plain top-3 by relevance --")
for doc_id, text in zip(candidate_ids[:3], candidate_texts[:3]):
    print(f"({doc_id}) {text}")

mmr_selected = mmr(query_vec, candidate_ids, candidate_vecs, candidate_texts, k=3)
print("\\n-- MMR-selected top-3 (diversity-aware) --")
for i in mmr_selected:
    print(f"({candidate_ids[i]}) {candidate_texts[i]}")
print("\\nPlain top-3 often clusters around one topic (e.g. all warranty); MMR spreads the "
      "picks across topics (warranty, returns, company) while still respecting relevance.")
""")

# ===========================================================================
# 11. Query rewriting
# ===========================================================================
md("""
## 11. Query rewriting

**What it is:** Use an LLM to rewrite the user's raw query into a
cleaner, retrieval-friendly version before embedding/searching — fixing
typos, expanding abbreviations, and making implicit intent explicit.

**When it's best used:** Real-world user input: typos, shorthand,
fragment-y phrasing, chat-style follow-ups ("what about the pro one?")
that don't stand alone well as a search query.

**Popularity:** High and rising — a very common first step in
production RAG pipelines, especially for consumer-facing chat products.

**Pros:** Meaningfully improves retrieval quality on messy real input;
cheap (one small LLM call); easy to combine with anything else here.
**Cons:** Adds LLM latency/cost per query; a bad rewrite can occasionally
drift away from the user's actual intent.

**Should it be in your advanced-RAG stack?** Yes, especially for
consumer-facing chat interfaces where raw user input is often messy.
""")

code("""
# ---- Query rewriting: clean up a messy/shorthand query with an LLM ----
messy_query = QUERIES["query_rewriting"]

rewrite_prompt = (
    "Rewrite the following user search query into a clear, well-formed question "
    "suitable for searching a company knowledge base. Fix typos and shorthand, "
    "but do not add information the user didn't ask about. "
    f"Return ONLY the rewritten question.\\n\\nUser query: {messy_query!r}"
)
rewritten = llm.invoke(rewrite_prompt).content.strip()

print(f"Raw query:      {messy_query!r}")
print(f"Rewritten query: {rewritten!r}\\n")

print("-- Retrieval with the RAW query --")
raw_hits = kb_collection.query(query_embeddings=[embeddings.embed_query(messy_query)], n_results=2)
for doc in raw_hits["documents"][0]:
    print("-", doc)

print("\\n-- Retrieval with the REWRITTEN query --")
rewritten_hits = kb_collection.query(query_embeddings=[embeddings.embed_query(rewritten)], n_results=2)
for doc in rewritten_hits["documents"][0]:
    print("-", doc)
""")

# ===========================================================================
# 12. Multi-query retrieval
# ===========================================================================
md("""
## 12. Multi-query retrieval

**What it is:** Ask an LLM to generate several *different phrasings* of
the same underlying question, run retrieval separately for each phrasing,
then merge/dedupe the combined result set. Different phrasings surface
different documents that a single embedding might miss.

**When it's best used:** Broad or compound questions where one phrasing
may not lexically/semantically overlap with how the answer is written in
the KB.

**Popularity:** High — this is LangChain's `MultiQueryRetriever` pattern,
common in production systems handling varied user phrasing.

**Pros:** Increases recall meaningfully, especially for vocabulary
mismatch between question and documents; easy to parallelize.
**Cons:** Multiple embedding/search calls per user query (higher latency
and cost); needs a merge/dedup step afterward (see deduplication above).

**Should it be in your advanced-RAG stack?** Yes for recall-sensitive use
cases (compound or ambiguous questions); optional for narrow, single-fact
questions where recall isn't the bottleneck.
""")

code("""
# ---- Multi-query retrieval: generate variants, retrieve for each, merge ----
query = QUERIES["multi_query"]

multi_query_prompt = (
    "Generate 3 different phrasings of the following question, each on its own line, "
    "no numbering, exploring different aspects if the question is compound. "
    f"Question: {query!r}"
)
variants_raw = llm.invoke(multi_query_prompt).content.strip()
variants = [line.strip("- ").strip() for line in variants_raw.split("\\n") if line.strip()]

print(f"Original query: {query!r}\\n")
print("Generated variants:")
for v in variants:
    print(" -", v)

merged = {}
for v in [query] + variants:
    hits = kb_collection.query(query_embeddings=[embeddings.embed_query(v)], n_results=2)
    for doc_id, doc in zip(hits["ids"][0], hits["documents"][0]):
        merged[doc_id] = doc

print(f"\\n-- Merged unique results across original + {len(variants)} variants --")
for doc_id, doc in merged.items():
    print(f"({doc_id}) {doc}")
print("\\nCompare to a single-query search below, which alone often misses one side of a compound question:")
single_hits = kb_collection.query(query_embeddings=[embeddings.embed_query(query)], n_results=2)
for doc in single_hits["documents"][0]:
    print("-", doc)
""")

# ===========================================================================
# 13. Query decomposition
# ===========================================================================
md("""
## 13. Query decomposition

**What it is:** Break a single compound question into independent
sub-questions, retrieve separately for each sub-question, then combine
the retrieved context to answer the original question. Different from
multi-query (same intent, different phrasings) — decomposition splits a
question that genuinely has multiple distinct parts.

**When it's best used:** Multi-part questions joined by "and" / "also" /
conditionals ("is X covered, and how long would Y take") where each part
needs different evidence.

**Popularity:** Moderate-to-high in advanced RAG/agentic systems;
overkill for simple single-fact lookups.

**Pros:** Each sub-question gets focused, high-precision retrieval
instead of one blended (and diluted) search; handles genuinely compound
questions well.
**Cons:** Requires an LLM call to decompose, then N retrieval calls;
overhead not worth it for simple questions; final answer synthesis step
still needed.

**Should it be in your advanced-RAG stack?** Yes for systems that expect
genuinely multi-part user questions; skip it for narrow single-intent
Q&A bots.
""")

code("""
# ---- Query decomposition: split a compound question, retrieve per sub-question ----
query = QUERIES["query_decomposition"]

decompose_prompt = (
    "Break the following question into 2-4 independent, self-contained sub-questions "
    "that together would let you fully answer it. One sub-question per line, no numbering.\\n"
    f"Question: {query!r}"
)
subq_raw = llm.invoke(decompose_prompt).content.strip()
sub_questions = [line.strip("- ").strip() for line in subq_raw.split("\\n") if line.strip()]

print(f"Original compound question: {query!r}\\n")
print("Decomposed sub-questions:")
for sq in sub_questions:
    print(" -", sq)

print("\\nRetrieval per sub-question:")
for sq in sub_questions:
    hits = kb_collection.query(query_embeddings=[embeddings.embed_query(sq)], n_results=2)
    print(f"\\n  Sub-question: {sq!r}")
    for doc in hits["documents"][0]:
        print("   ->", doc)
""")

# ===========================================================================
# 14. Relevance grading
# ===========================================================================
md("""
## 14. Relevance grading

**What it is:** After retrieval, use an LLM (or a smaller classifier) to
judge whether each retrieved document is actually relevant to the query,
and discard the ones that aren't — a quality gate between retrieval and
generation.

**When it's best used:** Whenever a query might have no good answer in
the KB at all (off-topic questions), so the system can say "I don't know"
instead of forcing an answer from irrelevant top-k results.

**Popularity:** High in agentic/self-correcting RAG designs (e.g.
"Self-RAG", "Corrective RAG") — a core building block of these patterns.

**Pros:** Prevents hallucinated answers built on irrelevant context;
enables graceful "I don't know" or fallback-to-web behavior.
**Cons:** Extra LLM call per retrieved document (or a batched call);
adds latency; grading quality depends on the grading prompt/model.
""")

code("""
# ---- Relevance grading: an off-topic query against the Aurora KB ----
query = QUERIES["relevance_grading"]
hits = kb_collection.query(query_embeddings=[embeddings.embed_query(query)], n_results=3)

print(f"Query: {query!r}  (note: this has nothing to do with Aurora Robotics)\\n")
print("-- Raw top-3 retrieved (retrieval always returns *something*) --")
for doc in hits["documents"][0]:
    print("-", doc)

grade_prompt_template = (
    "Question: {question}\\nDocument: {document}\\n"
    "Is this document relevant to answering the question? Answer with only YES or NO."
)

print("\\n-- Relevance grading pass --")
any_relevant = False
for doc in hits["documents"][0]:
    grade = llm.invoke(grade_prompt_template.format(question=query, document=doc)).content.strip().upper()
    print(f"[{grade}] {doc}")
    if grade.startswith("Y"):
        any_relevant = True

if not any_relevant:
    print("\\nAll candidates graded NOT relevant -> the system should say "
          "'I don't know' or fall back to web search, instead of forcing an answer.")
""")

# ===========================================================================
# 15. Iterative retrieval
# ===========================================================================
md("""
## 15. Iterative retrieval

**What it is:** Retrieve, let the LLM assess whether it has enough
information to answer, and if not, generate a follow-up query and
retrieve again — looping until enough evidence is gathered (or a max
iteration count is hit). Combines relevance grading + query rewriting
into a loop instead of a single retrieval pass.

**When it's best used:** Multi-hop questions where the first retrieval
only gets you "halfway" to the answer and reveals what to search for
next (e.g. "how long does the WHOLE process take" needs claim review
time AND repair turnaround time, which live in different KB entries).

**Popularity:** Moderate; the core idea behind agentic RAG loops
(e.g. LangGraph retrieval-agent patterns) rather than naive single-shot
RAG.

**Pros:** Handles multi-hop questions naive single-pass retrieval can't;
self-correcting if the first retrieval was insufficient.
**Cons:** Variable latency (unbounded without a max-iteration cap); more
complex control flow than any single technique above.

**Should it be in your advanced-RAG stack?** Yes for multi-hop or
research-style question answering; unnecessary overhead for simple
single-fact lookups.
""")

code("""
# ---- Iterative retrieval: retrieve, self-assess, retrieve again if needed ----
query = QUERIES["iterative_retrieval"]
max_iterations = 3
collected_docs = []
current_query = query

for iteration in range(1, max_iterations + 1):
    hits = kb_collection.query(query_embeddings=[embeddings.embed_query(current_query)], n_results=2)
    new_docs = hits["documents"][0]
    collected_docs.extend([d for d in new_docs if d not in collected_docs])

    print(f"-- Iteration {iteration}: searched {current_query!r} --")
    for d in new_docs:
        print("  ->", d)

    assess_prompt = (
        f"Original question: {query!r}\\n"
        f"Context gathered so far:\\n" + "\\n".join(f"- {d}" for d in collected_docs) + "\\n\\n"
        "Is this enough context to fully answer the original question? "
        "Reply on the first line with YES or NO. "
        "If NO, on the second line write ONE follow-up search query that would fill the gap."
    )
    assessment = llm.invoke(assess_prompt).content.strip().split("\\n")
    verdict = assessment[0].strip().upper()
    print(f"  Assessment: {verdict}")

    if verdict.startswith("Y") or len(assessment) < 2:
        print("\\nEnough context gathered - stopping the loop.")
        break
    current_query = assessment[1].strip()
    print(f"  Follow-up query: {current_query!r}\\n")

print(f"\\nFinal collected context ({len(collected_docs)} passages):")
for d in collected_docs:
    print("-", d)
""")

# ===========================================================================
# 16. SQL retrieval
# ===========================================================================
md("""
## 16. SQL retrieval

**What it is:** Instead of vector search, translate a natural-language
question into a SQL query (usually via an LLM) and run it against a
structured database table, returning exact rows as the retrieved
"context".

**When it's best used:** Questions about structured, tabular facts —
prices, stock counts, dates, aggregates — that vector search over prose
text handles poorly (embeddings are bad at "how many" / "what's the
exact price").

**Popularity:** High in enterprise RAG/"chat with your data" products
that sit on top of relational databases (a distinct sub-field, "Text-to-
SQL").

**Pros:** Exact, verifiable answers for structured data; can answer
aggregate questions (counts, sums, comparisons) that plain retrieval
cannot.
**Cons:** Generated SQL must be validated/sandboxed (SQL-injection-style
risk if executed against a real production DB); brittle to schema
changes; wrong table/column names in the LLM's output cause failures.

**Should it be in your advanced-RAG stack?** Yes, whenever part of your
knowledge base is genuinely structured/tabular data rather than prose.
""")

code("""
# ---- SQL retrieval: text-to-SQL against the Aurora product catalog ----
conn = sqlite3.connect(":memory:")
cur = conn.cursor()
cur.execute('''
    CREATE TABLE product_catalog (
        product_name TEXT, category TEXT, price_usd REAL, stock_units INTEGER, warehouse TEXT
    )
''')
cur.executemany("INSERT INTO product_catalog VALUES (?, ?, ?, ?, ?)", PRODUCT_CATALOG)
conn.commit()

query = QUERIES["sql_retrieval"]
schema_description = (
    "Table product_catalog(product_name TEXT, category TEXT, price_usd REAL, "
    "stock_units INTEGER, warehouse TEXT)"
)
sql_prompt = (
    f"Given this SQLite schema:\\n{schema_description}\\n\\n"
    f"Write ONE SQLite query (no markdown, no explanation, just SQL) to answer: {query!r}"
)
generated_sql = llm.invoke(sql_prompt).content.strip().strip("`").replace("sql\\n", "")

print(f"Query: {query!r}\\n")
print(f"Generated SQL:\\n{generated_sql}\\n")

rows = cur.execute(generated_sql).fetchall()
print("Result rows:")
for row in rows:
    print(" ", row)
conn.close()
""")

# ===========================================================================
# 17. Web fallback
# ===========================================================================
md("""
## 17. Web fallback

**What it is:** When the internal knowledge base doesn't contain the
answer (caught by relevance grading, above), fall back to a real-time web
search API instead of hallucinating or refusing outright.

**When it's best used:** Questions about anything time-sensitive or
outside the KB's scope (news, regulatory changes, competitor
information) that a static internal KB will never contain.

**Popularity:** High in consumer-facing assistants (Perplexity-style
products); moderate in enterprise RAG, gated behind explicit fallback
logic rather than always-on.

**Pros:** Extends coverage far beyond the static KB; keeps answers
current instead of frozen at ingestion time.
**Cons:** Less control over source quality/trust than a curated KB; adds
external API latency/cost; needs its own citation/attribution handling.

**Should it be in your advanced-RAG stack?** Yes, as a fallback path
(not primary retrieval) for any assistant that will realistically be
asked about things outside its curated KB.
""")

code("""
# ---- Web fallback: a real Tavily search call for a question the KB can't answer ----
import requests

query = QUERIES["web_fallback"]
kb_hits = kb_collection.query(query_embeddings=[embeddings.embed_query(query)], n_results=2)

print(f"Query: {query!r}\\n")
print("-- Best the internal KB can offer (not actually relevant) --")
for doc in kb_hits["documents"][0]:
    print("-", doc)

assert os.environ.get("TAVILY_API_KEY"), "TAVILY_API_KEY not found - check your .env"
response = requests.post(
    "https://api.tavily.com/search",
    json={"api_key": os.environ["TAVILY_API_KEY"], "query": query, "max_results": 3},
    timeout=20,
)
response.raise_for_status()
web_results = response.json()["results"]

print("\\n-- Real-time web search fallback (Tavily) --")
for r in web_results:
    print(f"- {r['title']}\\n  {r['url']}\\n  {r['content'][:200]}...")
""")

# ===========================================================================
# 18. Experimental features
# ===========================================================================
md("""
## 18. Experimental / advanced features

These techniques are real and used in some production systems, but are
more advanced, less universally needed, and sometimes still evolving in
best practice. Each gets a short what/when + a runnable example, treated
the same way as the sections above, just more briefly.
""")

md("""
### 18a. HyDE (Hypothetical Document Embeddings)

**What it is:** Ask an LLM to write a *hypothetical answer* to the query
first, then embed that hypothetical answer (instead of the query itself)
and use it to search — answers tend to be lexically/semantically closer
to real documents than short questions are.

**When best used:** Short, sparse queries where the question's wording is
very different from how the answer is phrased in the documents.
**Popularity:** Moderate — well-known research technique, seen in some
production systems but not universal.
**Pros:** Can improve recall on terse queries. **Cons:** Extra LLM call;
the hypothetical answer can hallucinate specifics that skew the search.
**In your stack?** Worth trying if you have short/sparse queries and
already accept LLM-call latency elsewhere in the pipeline; not a
must-have.
""")

code("""
# ---- HyDE: embed a hypothetical answer instead of the raw query ----
query = "battery storage advice"
hyde_prompt = f"Write a short, plausible-sounding answer (2-3 sentences) to this question, even if you're not sure: {query!r}"
hypothetical_answer = llm.invoke(hyde_prompt).content.strip()

print(f"Query: {query!r}")
print(f"Hypothetical answer: {hypothetical_answer!r}\\n")

print("-- Search using the raw query --")
for doc in kb_collection.query(query_embeddings=[embeddings.embed_query(query)], n_results=2)["documents"][0]:
    print("-", doc)

print("\\n-- Search using the HyDE hypothetical-answer embedding --")
for doc in kb_collection.query(query_embeddings=[embeddings.embed_query(hypothetical_answer)], n_results=2)["documents"][0]:
    print("-", doc)
""")

md("""
### 18b. Semantic chunking

**What it is:** Split documents at points where the *meaning* shifts
(detected by comparing embedding similarity between consecutive
sentences), instead of at a fixed character/token count.

**When best used:** Long, topically-varied documents where fixed-size
chunking would cut a coherent idea in half. (Already demonstrated in
`notebook.ipynb` step a — shown briefly here for completeness.)
**Popularity:** Moderate-high, growing. **Pros:** Chunks align with real
topic boundaries. **Cons:** Slower (embeds every sentence first); more
complex than fixed-size splitting.
**In your stack?** Yes for long, heterogeneous documents; overkill for
already-short, single-topic passages like this notebook's KB entries.
""")

code("""
# ---- Semantic chunking on the Aurora handbook's Section 1 (already covered in notebook.ipynb) ----
from langchain_experimental.text_splitter import SemanticChunker

section1_text = " ".join(HANDBOOK_SECTIONS[0]["paragraphs"])
semantic_splitter = SemanticChunker(embeddings)
semantic_chunks = semantic_splitter.split_text(section1_text)

print(f"Section 1 as ONE fixed block: {len(section1_text)} chars\\n")
print(f"Semantic chunker produced {len(semantic_chunks)} chunk(s):")
for i, c in enumerate(semantic_chunks):
    print(f"[{i}] ({len(c)} chars) {c[:150]}...")
""")

md("""
### 18c. Multi-vector retrieval

**What it is:** Store *multiple* embedding vectors per document (e.g. one
for the full text, one for a generated summary, one per key entity)
instead of a single vector — any of them can be matched at query time,
all pointing back to the same source document.

**When best used:** Documents that are long or multi-faceted enough that
one embedding can't represent everything the document might be searched
for.
**Popularity:** Moderate — supported by LangChain's `MultiVectorRetriever`
but less commonly reached for than parent-child retrieval, which solves a
similar problem more simply.
**Pros:** More surface area for a match; can combine full-text + summary
vectors. **Cons:** More storage and indexing complexity; summary
generation adds an LLM call at ingestion time.
**In your stack?** Situational — try parent-child retrieval first; reach
for this when a document is searched for via genuinely different facets
(e.g. its topic AND specific numbers within it).
""")

code("""
# ---- Multi-vector retrieval: index a document by both its full text AND a generated summary ----
doc_text = KB_DOCUMENTS[1]["text"]  # the Nimbus X200 Pro spec sheet
summary_prompt = f"Summarize this in 5 words or fewer: {doc_text!r}"
summary = llm.invoke(summary_prompt).content.strip()

full_vec = embeddings.embed_query(doc_text)
summary_vec = embeddings.embed_query(summary)

multi_vector_collection = chroma_client.get_or_create_collection("aurora_multivector_demo")
multi_vector_collection.add(
    ids=["nimbus_pro_full", "nimbus_pro_summary"],
    embeddings=[full_vec, summary_vec],
    documents=[doc_text, doc_text],  # both vectors point back to the SAME source document
    metadatas=[{"vector_type": "full"}, {"vector_type": "summary"}],
)

print(f"Full text: {doc_text!r}")
print(f"Generated summary vector's text: {summary!r}\\n")

query = "6-sided obstacle avoidance"
hits = multi_vector_collection.query(query_embeddings=[embeddings.embed_query(query)], n_results=2)
for doc_id, meta in zip(hits["ids"][0], hits["metadatas"][0]):
    print(f"Matched via {meta['vector_type']} vector -> ({doc_id})")
""")

md("""
### 18d. Hypothetical-question indexing

**What it is:** For each document, use an LLM to generate the questions
it would answer, embed *those questions* (not the document text), and
index them pointing back to the source document — at query time, match
the user's question directly against these hypothetical questions.

**When best used:** FAQ-style or support-ticket knowledge bases where
users literally ask questions, so matching question-to-question is more
direct than matching question-to-statement.
**Popularity:** Moderate — a known pattern, less common than plain dense
retrieval but effective for Q&A-style corpora specifically.
**Pros:** Question-to-question matching is often a tighter semantic match
than question-to-statement. **Cons:** Requires an LLM call per document
at ingestion time; quality depends on how well the generated questions
anticipate real user phrasing.
**In your stack?** Worth it specifically for FAQ-shaped content; less
useful for narrative/policy documents.
""")

code("""
# ---- Hypothetical-question indexing over one KB passage ----
doc_text = KB_DOCUMENTS[7]["text"]  # battery storage passage
gen_questions_prompt = f"Write 3 short questions this statement directly answers, one per line: {doc_text!r}"
generated_questions = [q.strip("- ").strip() for q in llm.invoke(gen_questions_prompt).content.strip().split("\\n") if q.strip()]

print(f"Source document: {doc_text!r}\\n")
print("Generated hypothetical questions (these get embedded, not the document):")
for q in generated_questions:
    print(" -", q)

hq_collection = chroma_client.get_or_create_collection("aurora_hypothetical_questions")
hq_vectors = embeddings.embed_documents(generated_questions)
hq_collection.add(
    ids=[f"hq_{i}" for i in range(len(generated_questions))],
    embeddings=hq_vectors,
    documents=[doc_text] * len(generated_questions),  # all point back to the same source doc
)

user_question = QUERIES["dense"]
hits = hq_collection.query(query_embeddings=[embeddings.embed_query(user_question)], n_results=1)
print(f"\\nUser question: {user_question!r}")
print(f"Matched via a hypothetical question, returns source document:\\n{hits['documents'][0][0]!r}")
""")

md("""
### 18e. Contextualized chunks

**What it is:** Before embedding a chunk, prepend a short LLM-generated
summary of *where this chunk sits in the broader document* (e.g. "This
paragraph is from the Warranty Claim Process section of the Aurora
handbook, describing repair turnaround time.") so the chunk's own
embedding carries context it wouldn't have in isolation.

**When best used:** Small chunks pulled from long documents, where the
chunk alone is ambiguous without knowing what section/document it's part
of (Anthropic's "contextual retrieval" write-up popularized this).
**Popularity:** Growing — increasingly common in advanced RAG systems
after Anthropic's contextual-retrieval research showed clear recall
gains.
**Pros:** Meaningfully improves recall for small, decontextualized
chunks; simple to add on top of any existing chunking pipeline.
**Cons:** One extra LLM call per chunk at ingestion time (cost scales
with corpus size, though can be cached/batched).
**In your stack?** Yes for large document sets built from small chunks —
one of the higher-ROI additions among the experimental techniques here.
""")

code("""
# ---- Contextualized chunks: prepend document context before embedding ----
raw_chunk = HANDBOOK_SECTIONS[1]["paragraphs"][2]  # repair turnaround paragraph, ambiguous alone
context_prompt = (
    f"Document: Aurora Robotics Warranty Handbook, Section '{HANDBOOK_SECTIONS[1]['heading']}'.\\n"
    f"Write ONE short sentence (under 20 words) situating this paragraph within that section, "
    f"to prepend before the paragraph text: {raw_chunk!r}"
)
context_prefix = llm.invoke(context_prompt).content.strip()
contextualized_chunk = f"{context_prefix} {raw_chunk}"

print(f"Raw chunk (ambiguous alone): {raw_chunk!r}\\n")
print(f"Contextualized chunk: {contextualized_chunk!r}\\n")

query = "how fast do I get my drone back after a warranty repair"
raw_sim = cosine_sim(embeddings.embed_query(query), embeddings.embed_query(raw_chunk))
contextualized_sim = cosine_sim(embeddings.embed_query(query), embeddings.embed_query(contextualized_chunk))
print(f"Similarity to query using RAW chunk:            {raw_sim:.4f}")
print(f"Similarity to query using CONTEXTUALIZED chunk: {contextualized_sim:.4f}")
""")

md("""
### 18f. Knowledge-graph retrieval

**What it is:** Extract entities and relationships from documents into a
graph (e.g. `Nimbus X200 --[has_accessory]--> Replacement Battery`,
`Aurora Care+ --[extends]--> Warranty`), then answer queries by
traversing the graph instead of (or alongside) vector search.

**When best used:** Questions genuinely about *relationships* between
entities ("what add-ons affect the warranty?") that a single passage of
text may not state directly, but which fall out of connecting several
facts.
**Popularity:** Moderate and growing, but real engineering investment
(entity extraction, graph storage/query layer) — much heavier than
vector search alone.
**Pros:** Handles multi-hop relational questions vector search struggles
with; graph structure is interpretable/auditable.
**Cons:** Significant build cost (extraction pipeline + graph DB);
brittleness if entity extraction misses or mislabels relationships.
**In your stack?** Only if your domain genuinely has rich entity
relationships worth querying — overkill for mostly-prose FAQ/policy
content like this notebook's KB.
""")

code("""
# ---- Knowledge-graph retrieval: a tiny in-memory graph, traversed for a relational question ----
graph_edges = [
    ("Nimbus X200", "has_variant", "Nimbus X200 Pro"),
    ("Nimbus X200 Pro", "has_feature", "6-sided obstacle avoidance"),
    ("Aurora Care+", "extends", "Warranty"),
    ("Aurora Care+", "covers", "Accidental crash (2/year)"),
    ("Warranty", "excludes", "Crash damage"),
    ("Warranty", "excludes", "Water damage"),
    ("Nimbus X200", "compatible_with", "Replacement Battery (Nimbus)"),
]

def graph_traverse(start_entity, edges):
    return [(s, rel, o) for s, rel, o in edges if s == start_entity or o == start_entity]

query_entity = "Aurora Care+"
print(f"Relational query: what does {query_entity!r} affect?\\n")
for s, rel, o in graph_traverse(query_entity, graph_edges):
    print(f"  {s} --[{rel}]--> {o}")
print("\\nA single passage of text rarely states 'Aurora Care+ affects the warranty AND covers crashes' "
      "as one fact - the graph makes both relationships explicit and traversable.")
""")

md("""
### 18g. GraphRAG

**What it is:** A specific, more elaborate knowledge-graph approach
(popularized by Microsoft's GraphRAG) that clusters the extracted graph
into communities/topics and pre-generates summaries per community, so
broad "give me the big picture" questions can be answered from
community summaries instead of traversing individual edges.

**When best used:** Very large corpora where you need holistic,
corpus-wide summarization questions answered well ("what are the main
themes across all support tickets?") — something neither plain vector
search nor a small entity graph handles well.
**Popularity:** Growing rapidly in enterprise/large-corpus RAG, but heavy
infrastructure (community detection, per-community summarization) not
justified for small or narrow-domain KBs.
**Pros:** Strong at global/holistic summarization queries. **Cons:** Very
resource-intensive to build (community detection + LLM summarization per
community) and to maintain as data changes.
**In your stack?** Not for a KB this small (20 passages) — this is
included so it's clear how it *differs* from the simple knowledge-graph
retrieval above (community-level summaries vs. individual edge lookups),
not something to actually run at this dataset's scale.
""")

code("""
# ---- GraphRAG-style idea (illustrative, not real community detection at this tiny scale) ----
# Group graph_edges into topic "communities" and pre-summarize each community with an LLM,
# rather than traversing individual edges as in 18f.
communities = {
    "warranty_and_addons": [e for e in graph_edges if "Warranty" in e or "Care+" in e[0]],
    "product_lineup": [e for e in graph_edges if "Nimbus" in e[0] or "Nimbus" in e[2]],
}

for name, edges in communities.items():
    edges_text = "; ".join(f"{s} {rel} {o}" for s, rel, o in edges)
    summary_prompt = f"In one sentence, summarize what this set of facts is about: {edges_text}"
    community_summary = llm.invoke(summary_prompt).content.strip()
    print(f"Community '{name}': {community_summary}")

print("\\nA broad question like 'summarize Aurora's product+warranty ecosystem' can be answered "
      "from these 2 pre-built community summaries instead of traversing every edge individually.")
""")

md("""
### 18h. LLM reranking

**What it is:** Like cross-encoder reranking, but using a general-purpose
LLM (via prompting) to score or reorder candidates instead of a
purpose-trained cross-encoder model.

**When best used:** When you want reranking logic that can consider
nuanced/instructional criteria (e.g. "prefer the most recent policy
document") that a generic cross-encoder wasn't trained to weigh.
**Popularity:** Moderate — used in some pipelines instead of/alongside a
cross-encoder, but slower and pricier per candidate.
**Pros:** Flexible - can rerank on custom criteria via prompting, not
just generic relevance. **Cons:** Much slower and more expensive per
candidate pair than a small cross-encoder model; less consistent scoring
across calls than a fixed model.
**In your stack?** Prefer the cross-encoder (section 8) as the default;
reach for LLM reranking only when you need custom, instruction-driven
ranking criteria a cross-encoder can't express.
""")

code("""
# ---- LLM reranking: rank by 'most recent' as a custom criterion a cross-encoder can't express ----
query = "What's Aurora's current return policy?"
candidates = kb_collection.query(query_embeddings=[embeddings.embed_query(query)], n_results=3)
candidate_texts = candidates["documents"][0]
candidate_metas = candidates["metadatas"][0]

candidates_block = "\\n".join(
    f"{i}. (date: {m['date']}) {t}" for i, (t, m) in enumerate(zip(candidate_texts, candidate_metas))
)
rerank_prompt = (
    f"Question: {query!r}\\n\\nCandidates:\\n{candidates_block}\\n\\n"
    "Rank these candidates by which is MOST RECENT and still relevant to the question. "
    "Return only the candidate numbers in ranked order, comma-separated."
)
ranking = llm.invoke(rerank_prompt).content.strip()

print(f"Query: {query!r}\\n")
print("Candidates (with dates):")
print(candidates_block)
print(f"\\nLLM's recency-aware ranking (by index): {ranking}")
""")

md("""
### 18i. Contextual compression

**What it is:** After retrieving full documents/chunks, run an LLM (or
extractive model) pass that strips each one down to only the sentences
actually relevant to the query, before passing them to the generation
step — same document count, far fewer irrelevant tokens per document.

**When best used:** Long retrieved chunks where only a small part is
actually relevant to the specific question asked, and the rest is noise
that costs context-window budget.
**Popularity:** Moderate — LangChain ships `ContextualCompressionRetriever`
for this; used in cost/latency-sensitive production pipelines.
**Pros:** Reduces tokens sent to the generator, which lowers cost and
can reduce distraction from irrelevant surrounding text.
**Cons:** Extra LLM call per document; risk of over-compressing and
losing context the generator actually needed.
**In your stack?** Worth it when retrieved chunks are long/multi-topic;
not needed here since this notebook's KB passages are already short and
single-topic.
""")

code("""
# ---- Contextual compression on a longer, multi-fact passage ----
long_passage = (
    "Aurora Robotics was founded in 2019 and is headquartered in Austin, Texas, with a "
    "secondary office in Rotterdam. The Nimbus X200 uses a 1/1.3-inch CMOS sensor. "
    "Custom-configured drones with engraved plates are final sale and cannot be returned. "
    "The company publishes quarterly sustainability reports on battery recycling."
)
query = "Can I return a custom-engraved drone?"

compress_prompt = (
    f"Question: {query!r}\\nPassage: {long_passage!r}\\n\\n"
    "Extract ONLY the sentence(s) from the passage relevant to answering the question. "
    "Return just that text, nothing else."
)
compressed = llm.invoke(compress_prompt).content.strip()

print(f"Query: {query!r}\\n")
print(f"Full passage ({len(long_passage)} chars):\\n{long_passage}\\n")
print(f"Compressed passage ({len(compressed)} chars):\\n{compressed}")
""")

# ===========================================================================
# 19. Putting it all together
# ===========================================================================
md("""
## 19. Putting it all together: a recommended retrieval pipeline

No single technique above is "the" answer — production RAG systems layer
several together. Given everything demonstrated above, here is a
sensible default pipeline for a KB shaped like Aurora's (mixed prose +
structured data, moderate size, real users typing messy questions):

```text
User query
   |
   v
+-------------------+
| Query rewriting     |  fix typos/shorthand (section 11)
+-------------------+
   |
   v
+-------------------+
| Route: text vs SQL   |  is this a structured-data question? (section 16)
+-------------------+
   |                \\
   | text             \\ structured
   v                   v
+-----------------+   +------------------+
| Multi-query      |   | Text-to-SQL      |
| generation (12)  |   | retrieval (16)   |
+-----------------+   +------------------+
   |
   v
+-----------------------------+
| Hybrid retrieval per variant  |  dense (1) + BM25 (2) (section 3)
+-----------------------------+
   |
   v
+-------------------+
| RRF fusion          |  merge dense+sparse+multi-query lists (section 7)
+-------------------+
   |
   v
+-------------------+
| Deduplication       |  drop near-duplicate passages (section 9)
+-------------------+
   |
   v
+-------------------+
| Cross-encoder rerank |  precision pass over top-k (section 8)
+-------------------+
   |
   v
+-------------------+
| Relevance grading    |  discard anything still irrelevant (section 14)
+-------------------+
   |            \\
   | relevant     \\ nothing relevant
   v               v
+-----------+   +----------------+
| Generate  |   | Web fallback    |  (section 17)
| answer    |   | then generate  |
+-----------+   +----------------+
```

Notes on this ordering:
- **Query rewriting first** — every downstream step benefits from a
  cleaner query, so it's cheap to do once, up front.
- **Route text vs. SQL early** — no point running vector search against
  a "how many units in stock" question.
- **Multi-query -> hybrid -> RRF** happens before reranking, because
  reranking is expensive per-candidate and should only run once over the
  final fused/deduped candidate list, not once per variant.
- **Relevance grading gates the fallback** — this is what makes "web
  fallback" safe to wire in at all, instead of always calling the web API.
- **Parent-child / neighbor expansion / contextualization** are not shown
  as pipeline *stages* here because they're ingestion-time or
  retrieval-shape decisions (how a document is chunked/indexed), not
  extra steps in the per-query flow above — you choose them when you
  build the index, not when you answer a query.
- **MMR** is optional and situational (section 10) — use it in place of
  the plain top-k cut when the query is broad/exploratory rather than a
  narrow factual lookup.
""")

code("""
# ---- Final example: the recommended pipeline end to end, on a genuinely compound question ----
final_query = "What's Aurora's return window for an unopened Nimbus, and how many Nimbus X200 units are in stock in Austin?"
print(f"User query: {final_query!r}\\n")

# 1. Query rewriting (already clean here, but always run it)
rewritten = llm.invoke(
    f"Rewrite this into a clear, well-formed question, fixing only typos/shorthand if any: {final_query!r}"
).content.strip()
print(f"1. Rewritten query: {rewritten!r}")

# 2. Decompose into text-part and SQL-part (routing)
decompose_prompt = (
    f"Question: {rewritten!r}\\nSplit this into its TEXT/POLICY sub-question and its "
    "STRUCTURED-DATA/STOCK sub-question. Reply in exactly this format:\\n"
    "TEXT: <sub-question>\\nSQL: <sub-question>"
)
route = llm.invoke(decompose_prompt).content.strip()
print(f"\\n2. Routing decomposition:\\n{route}")
text_subq = [l for l in route.split("\\n") if l.startswith("TEXT:")][0].replace("TEXT:", "").strip()
sql_subq = [l for l in route.split("\\n") if l.startswith("SQL:")][0].replace("SQL:", "").strip()

# 3. Text path: hybrid retrieval -> RRF -> dedup -> cross-encoder rerank -> relevance grade
dense_ids = kb_collection.query(query_embeddings=[embeddings.embed_query(text_subq)], n_results=len(kb_ids))["ids"][0]
bm25_ids = [doc_id for doc_id, _ in sorted(zip(kb_ids, bm25.get_scores(tokenize(text_subq))), key=lambda x: x[1], reverse=True)]
fused = rrf_fuse([dense_ids, bm25_ids])[:5]
fused_texts = [text_by_id[doc_id] for doc_id, _ in fused]

pairs = [(text_subq, t) for t in fused_texts]
rerank_scores = reranker.predict(pairs)
top_text_doc = sorted(zip(fused_texts, rerank_scores), key=lambda x: x[1], reverse=True)[0][0]

grade = llm.invoke(
    f"Question: {text_subq!r}\\nDocument: {top_text_doc!r}\\nIs this relevant? Answer YES or NO."
).content.strip().upper()
print(f"\\n3. Text sub-question: {text_subq!r}")
print(f"   Top passage after hybrid+RRF+rerank: {top_text_doc!r}")
print(f"   Relevance grade: {grade}")

# 4. SQL path: text-to-SQL
sql_gen = llm.invoke(
    f"Given this SQLite schema:\\n{schema_description}\\nWrite ONE SQLite query (no markdown) to answer: {sql_subq!r}"
).content.strip().strip("`").replace("sql\\n", "")
conn2 = sqlite3.connect(":memory:")
c2 = conn2.cursor()
c2.execute("CREATE TABLE product_catalog (product_name TEXT, category TEXT, price_usd REAL, stock_units INTEGER, warehouse TEXT)")
c2.executemany("INSERT INTO product_catalog VALUES (?, ?, ?, ?, ?)", PRODUCT_CATALOG)
sql_cursor = c2.execute(sql_gen)
sql_columns = [d[0] for d in sql_cursor.description]
sql_rows = sql_cursor.fetchall()
sql_rows_labeled = [dict(zip(sql_columns, row)) for row in sql_rows]
conn2.close()
print(f"\\n4. SQL sub-question: {sql_subq!r}")
print(f"   Generated SQL: {sql_gen}")
print(f"   Result: {sql_rows_labeled}")

# 5. Final generation, combining both retrieved contexts
final_prompt = (
    f"Answer the user's question using ONLY this context.\\n\\n"
    f"Policy context: {top_text_doc}\\n"
    f"Stock data (each dict is one matching row, with named fields): {sql_rows_labeled}\\n\\n"
    f"User question: {final_query}"
)
final_answer = llm.invoke(final_prompt).content.strip()
print(f"\\n5. Final generated answer:\\n{final_answer}")
""")

md("""
### Revision summary

| Technique | One-line reminder |
|---|---|
| Dense semantic | Match by meaning via embeddings |
| Sparse BM25 | Match by exact keyword/term overlap |
| Hybrid | Run both, combine the results |
| Metadata filtering | Restrict by structured attributes before/with ranking |
| Parent-child | Match small, return big (section context) |
| Neighbor expansion | Grab the chunks next to the match |
| RRF | Fuse ranked lists by rank position, not raw score |
| Cross-encoder rerank | Score (query, doc) pairs jointly for precision |
| Deduplication | Drop near-identical retrieved passages |
| MMR | Trade relevance for topical diversity |
| Query rewriting | Clean up messy user input before searching |
| Multi-query | Search several phrasings, merge results |
| Query decomposition | Split compound questions, retrieve per part |
| Relevance grading | Judge and discard irrelevant retrieved docs |
| Iterative retrieval | Retrieve, self-assess, retrieve again if needed |
| SQL retrieval | Text-to-SQL for structured/tabular facts |
| Web fallback | Real-time search when the KB has nothing |
| HyDE | Embed a hypothetical answer, not the query |
| Semantic chunking | Split at meaning shifts, not fixed size |
| Multi-vector | Multiple embeddings per document |
| Hypothetical-question indexing | Index generated questions, not statements |
| Contextualized chunks | Prepend document context before embedding |
| Knowledge-graph retrieval | Traverse entities/relationships, not just vectors |
| GraphRAG | Community-level summaries for holistic questions |
| LLM reranking | Rerank via custom LLM-judged criteria |
| Contextual compression | Strip retrieved text to only the relevant sentences |
""")

nb["cells"] = cells
nbf.write(nb, "retrieval_techniques.ipynb")
print("Wrote retrieval_techniques.ipynb with", len(cells), "cells")
