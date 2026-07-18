"""Ingestion pipeline: extract text from files/URLs, chunk, embed, upsert.

Chunking strategies (selected per request via `chunking_strategy`):
- "recursive" (default): minimal reimplementation of
  langchain_text_splitters.RecursiveCharacterTextSplitter's approach —
  tries a list of separators (paragraph, line, sentence, word) in order,
  recursively splitting oversized pieces until each chunk is under
  chunk_size, with chunk_overlap carried between adjacent chunks.
- "character": fixed-size character windows with overlap, no
  separator-awareness.
- "token": tiktoken-based split (cl100k_base encoding), chunk_size in
  tokens rather than characters.
- "semantic": a simple sentence-embedding-distance splitter — sentences
  are embedded (using the same embedding_choice as the request) and
  consecutive sentences are grouped into a chunk until the cosine
  distance to the running chunk centroid exceeds a threshold, at which
  point a new chunk starts. This is a lightweight stand-in for
  langchain_experimental's SemanticChunker (not used here to avoid an
  extra heavy/experimental dependency for a teaching demo).

Reimplemented locally rather than depending on langchain_text_splitters,
to keep the dependency footprint small for a teaching demo.
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass, field

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader

from .embeddings import embed
from .vector_store import upsert_chunks

DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 150

SUPPORTED_CHUNKERS = ["recursive", "character", "token", "semantic"]


# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------

def extract_text_from_pdf(file_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(file_bytes))
    return "\n\n".join(page.extract_text() or "" for page in reader.pages)


def extract_text_from_plain(file_bytes: bytes) -> str:
    return file_bytes.decode("utf-8", errors="replace")


def extract_text_from_file(filename: str, file_bytes: bytes) -> str:
    lower = filename.lower()
    if lower.endswith(".pdf"):
        return extract_text_from_pdf(file_bytes)
    return extract_text_from_plain(file_bytes)


def extract_text_from_url(url: str) -> str:
    response = requests.get(url, timeout=20, headers={"User-Agent": "rag-demo/1.0"})
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Chunkers
# ---------------------------------------------------------------------------

def _split_recursive(text: str, chunk_size: int, overlap: int) -> list[str]:
    separators = ["\n\n", "\n", ". ", " ", ""]

    def _split(piece: str, seps: list[str]) -> list[str]:
        if len(piece) <= chunk_size:
            return [piece] if piece.strip() else []
        if not seps:
            return [piece[i : i + chunk_size] for i in range(0, len(piece), chunk_size)]
        sep, rest = seps[0], seps[1:]
        parts = piece.split(sep) if sep else list(piece)
        chunks: list[str] = []
        current = ""
        for part in parts:
            candidate = current + (sep if current else "") + part
            if len(candidate) <= chunk_size:
                current = candidate
            else:
                if current:
                    chunks.append(current)
                if len(part) > chunk_size:
                    chunks.extend(_split(part, rest))
                    current = ""
                else:
                    current = part
        if current:
            chunks.append(current)
        return chunks

    raw_chunks = _split(text, separators)
    return _apply_overlap(raw_chunks, overlap)


def _apply_overlap(chunks: list[str], overlap: int) -> list[str]:
    if overlap <= 0 or len(chunks) <= 1:
        return [c for c in chunks if c.strip()]
    result = []
    for i, chunk in enumerate(chunks):
        if i == 0:
            result.append(chunk)
        else:
            prefix = chunks[i - 1][-overlap:]
            result.append(prefix + chunk)
    return [c for c in result if c.strip()]


def _split_character(text: str, chunk_size: int, overlap: int) -> list[str]:
    step = max(chunk_size - overlap, 1)
    chunks = []
    for start in range(0, len(text), step):
        chunk = text[start : start + chunk_size]
        if chunk.strip():
            chunks.append(chunk)
        if start + chunk_size >= len(text):
            break
    return chunks


def _split_token(text: str, chunk_size: int, overlap: int) -> list[str]:
    import tiktoken

    enc = tiktoken.get_encoding("cl100k_base")
    tokens = enc.encode(text)
    step = max(chunk_size - overlap, 1)
    chunks = []
    for start in range(0, len(tokens), step):
        piece_tokens = tokens[start : start + chunk_size]
        chunk = enc.decode(piece_tokens)
        if chunk.strip():
            chunks.append(chunk)
        if start + chunk_size >= len(tokens):
            break
    return chunks


def _split_semantic(text: str, embedding_choice: str, distance_threshold: float = 0.35) -> list[str]:
    import numpy as np

    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    if len(sentences) <= 1:
        return [text] if text.strip() else []

    outcome = embed(sentences, embedding_choice)
    vectors = np.array(outcome.vectors)

    chunks: list[str] = []
    current_sentences = [sentences[0]]
    current_centroid = vectors[0]

    for i in range(1, len(sentences)):
        vec = vectors[i]
        denom = (np.linalg.norm(current_centroid) * np.linalg.norm(vec)) or 1e-9
        cosine_sim = float(np.dot(current_centroid, vec) / denom)
        cosine_distance = 1 - cosine_sim
        if cosine_distance > distance_threshold:
            chunks.append(" ".join(current_sentences))
            current_sentences = [sentences[i]]
            current_centroid = vec
        else:
            current_sentences.append(sentences[i])
            n = len(current_sentences)
            current_centroid = (current_centroid * (n - 1) + vec) / n

    if current_sentences:
        chunks.append(" ".join(current_sentences))
    return chunks


def chunk_text(
    text: str,
    strategy: str = "recursive",
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    embedding_choice: str = "openai-small",
) -> list[str]:
    if strategy == "recursive":
        return _split_recursive(text, chunk_size, chunk_overlap)
    if strategy == "character":
        return _split_character(text, chunk_size, chunk_overlap)
    if strategy == "token":
        return _split_token(text, chunk_size, chunk_overlap)
    if strategy == "semantic":
        return _split_semantic(text, embedding_choice)
    raise ValueError(f"Unsupported chunking_strategy: {strategy!r}. Supported: {SUPPORTED_CHUNKERS}")


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

@dataclass
class IngestSourceResult:
    source: str
    chunks_created: int


@dataclass
class IngestResult:
    sources: list[IngestSourceResult] = field(default_factory=list)
    total_chunks: int = 0
    embedding_tokens: int = 0
    embedding_cost_usd: float = 0.0


def ingest_sources(
    session_id: str,
    files: list[tuple[str, bytes]],
    url: str | None,
    chunking_strategy: str = "recursive",
    embedding_choice: str = "openai-small",
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> IngestResult:
    from .cost import embedding_cost

    result = IngestResult()

    raw_sources: list[tuple[str, str]] = []  # (source_name, text)
    for filename, file_bytes in files:
        raw_sources.append((filename, extract_text_from_file(filename, file_bytes)))
    if url:
        raw_sources.append((url, extract_text_from_url(url)))

    for source_name, text in raw_sources:
        chunks = chunk_text(
            text,
            strategy=chunking_strategy,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            embedding_choice=embedding_choice,
        )
        if not chunks:
            result.sources.append(IngestSourceResult(source=source_name, chunks_created=0))
            continue

        outcome = embed(chunks, embedding_choice)
        metadata = [
            {"source": source_name, "chunk_index": i} for i in range(len(chunks))
        ]
        upsert_chunks(session_id, embedding_choice, chunks, outcome.vectors, metadata)

        result.sources.append(IngestSourceResult(source=source_name, chunks_created=len(chunks)))
        result.total_chunks += len(chunks)
        result.embedding_tokens += outcome.tokens
        result.embedding_cost_usd += embedding_cost(outcome.model_name, outcome.tokens)

    return result
