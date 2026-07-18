"""Prompt construction + generation.

Default RAG prompt: a system-style instruction, the retrieved context
(numbered chunks with source), and the question, asking the model to
answer using only the provided context and say so if it can't.

Custom prompt override: a plain string containing both `{context}` and
`{question}` placeholders — validated at request time.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .llm_client import DEFAULT_CHAT_MODEL, chat_completion

_CITATION_MARKER_RE = re.compile(r"\[(\d+)\]")

DEFAULT_PROMPT_TEMPLATE = """You are a helpful assistant answering questions using only the \
retrieved context below. If the answer is not contained in the context, \
say you don't have enough information — do not make anything up.

Each context chunk is numbered like [1], [2], etc. Cite the chunk number(s) \
you actually used inline in your answer, right after the claim they support \
(e.g. "The budget is $4.2 million [1]."). Only cite chunks you drew on — \
do not cite a chunk you didn't use, and do not invent a chunk number that \
isn't in the context.

Context:
{context}

Question: {question}

Answer:"""


class InvalidPromptTemplateError(ValueError):
    pass


def validate_prompt_template(template: str) -> None:
    if "{context}" not in template or "{question}" not in template:
        raise InvalidPromptTemplateError(
            "Custom prompt_template must contain both '{context}' and '{question}' placeholders."
        )


def format_context(chunks: list[dict]) -> str:
    lines = []
    for i, chunk in enumerate(chunks, start=1):
        source = chunk.get("source", "unknown")
        lines.append(f"[{i}] (source: {source})\n{chunk.get('text', '')}")
    return "\n\n".join(lines)


@dataclass
class GenerationResult:
    answer: str
    prompt_tokens: int
    completion_tokens: int
    model: str


def generate_answer(
    question: str,
    chunks: list[dict],
    prompt_template: str | None = None,
    model: str = DEFAULT_CHAT_MODEL,
) -> GenerationResult:
    template = prompt_template or DEFAULT_PROMPT_TEMPLATE
    validate_prompt_template(template)

    context = format_context(chunks)
    prompt = template.format(context=context, question=question)

    result = chat_completion(
        [{"role": "user", "content": prompt}], model=model, temperature=0.2
    )
    return GenerationResult(
        answer=result.content,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        model=model,
    )


def build_citations(answer: str, chunks: list[dict]) -> list[dict]:
    """Map each [n] marker the model actually used in `answer` back to the
    source chunk it refers to (1-indexed, matching format_context's
    numbering). Only includes markers present in the answer text — a
    citation the model didn't cite isn't surfaced, and a marker number
    outside the retrieved chunk range is silently ignored (the model
    citing a chunk that doesn't exist is a prompt-adherence failure, not
    something to crash the response over)."""
    cited_numbers = sorted({int(n) for n in _CITATION_MARKER_RE.findall(answer)})
    citations = []
    for n in cited_numbers:
        idx = n - 1
        if 0 <= idx < len(chunks):
            chunk = chunks[idx]
            text = " ".join(chunk.get("text", "").split())  # collapse embedded newlines/whitespace
            citations.append(
                {
                    "marker": f"[{n}]",
                    "source": chunk.get("source", "unknown"),
                    "chunk_index": chunk.get("chunk_index"),
                    "snippet": text[:280] + ("..." if len(text) > 280 else ""),
                }
            )
    return citations
