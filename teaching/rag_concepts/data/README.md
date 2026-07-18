# Toy data

- `toy_corpus.py` — the shared toy text used across every notebook section:
  - `TOY_PARAGRAPH`: one paragraph about the Amazon rainforest, used for the
    chunking section (step a) so students can compare how different
    splitters break up the *same* text.
  - `TOY_DOCUMENTS`: 8 short toy documents across 3 topics (climate,
    deforestation, programming) with `topic`/`source` metadata, used from
    the vector-DB push (step e) through search/reranking/MMR (steps f-h)
    so every retrieval technique is demonstrated against the same data.
  - `TOY_WORD` / `TOY_QUERY`: single word and query string reused for the
    embedding comparison (step b) and search sections (step f).

No external files needed — everything is plain Python literals imported
directly into the notebook via `sys.path` + `from toy_corpus import ...`.

- `toy_document.pdf` / `toy_document.txt` — small toy files used in step i
  (document loading) to demonstrate `PyPDFLoader` and `TextLoader` on the
  same Amazon-rainforest topic as the rest of the notebook. The PDF was
  generated with `reportlab`.
