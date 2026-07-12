# Naive RAG End-to-End Pipeline (Teaching Notebook)

A progressive Jupyter notebook demonstrating a naive Retrieval-Augmented
Generation (RAG) pipeline built with LangChain wrappers:

1. **Ingestion** — load PDF / URL / text documents (`PyPDFLoader`,
   `WebBaseLoader`, `TextLoader`), split with `RecursiveCharacterTextSplitter`.
2. **Embed + store** — embed chunks with OpenAI `text-embedding-3-small`,
   store in an in-memory ChromaDB collection.
3. **Query** — embed the user's question with the same embedding model,
   run similarity search, retrieve the top 3 chunks.
4. **Generate** — pass retrieved chunks + question to `gpt-4o-mini`, with a
   system prompt strictly requiring context-only answers.

## Setup

```bash
cd teaching/notebook_naive_rag
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m ipykernel install --user --name notebook_naive_rag_venv --display-name "notebook_naive_rag (.venv)"
```

Make sure `OPENAI_API_KEY` is set in the repo-root `.env` file (this
notebook loads it via `python-dotenv` from `../../.env`).

## Run

```bash
jupyter notebook notebook.ipynb
```

Select the `notebook_naive_rag (.venv)` kernel, then run all cells top to
bottom. Or execute headlessly:

```bash
jupyter nbconvert --to notebook --execute --output notebook.ipynb \
  --ExecutePreprocessor.kernel_name=notebook_naive_rag_venv notebook.ipynb
```

Edit the `SOURCES` list (ingestion cell) and `QUESTION` variable (query
cell) to try your own documents and questions. Two sample files are
included under `data/` (`company_handbook.txt`, `product_faq.pdf`) so the
notebook runs end to end with no setup.

## Verified against

- Provider/model: OpenAI, `text-embedding-3-small` (embeddings) +
  `gpt-4o-mini` (generation) — real API key verified with a live call.
- Vector store: ChromaDB, in-memory (`langchain-chroma`), no persistence.
- Observability: none (per teaching brief).
- Verified 2026-07-13 via `jupyter nbconvert --execute` end to end: 2
  sample documents loaded → 7 chunks → embedded and stored in Chroma →
  top-3 retrieval on a PTO question → correct, context-grounded answer
  returned by `gpt-4o-mini`.

## Extending

Use `/add-teaching-step notebook_naive_rag` to add further steps (e.g.
citing sources in the answer, swapping in a different vector store,
adding conversational memory) without disturbing the verified steps above.
