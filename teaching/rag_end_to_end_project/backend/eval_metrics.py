"""Per-answer RAG eval metrics.

Library choice: a scripted LLM-judge fallback, NOT the `ragas` package.
Ragas pulls in a large, fast-moving dependency tree (langchain core,
datasets, etc.) and is prone to breaking on small demo setups (empty/short
contexts, single-turn eval) — too heavy/fragile for a fast teaching build.
Instead this uses a single structured-output OpenAI call that scores
faithfulness, answer relevancy, and context precision on 0-1 scales given
the question, retrieved context, and generated answer. This keeps the eval
step to one extra LLM call with a predictable JSON shape.

Metrics:
- faithfulness: does the answer's content stay grounded in the retrieved
  context, without unsupported claims?
- answer_relevancy: does the answer actually address the question asked?
- context_precision: how much of the retrieved context was actually
  relevant/used, roughly approximating precision (recall is not
  computed — it needs a ground-truth answer set that a live demo doesn't
  have; noted as an omission from the full Ragas metric set).
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from .llm_client import chat_completion

EVAL_MODEL = "gpt-4o-mini"

EVAL_SYSTEM_PROMPT = """You are a strict RAG evaluation judge. Given a question, \
retrieved context, and a generated answer, score three metrics from 0.0 to 1.0:

- faithfulness: is the answer fully supported by the context, with no \
unsupported/hallucinated claims? 1.0 = fully grounded, 0.0 = mostly fabricated.
- answer_relevancy: does the answer directly address the question asked? \
1.0 = fully relevant, 0.0 = off-topic.
- context_precision: how relevant/useful is the retrieved context for \
answering the question? 1.0 = all context relevant, 0.0 = none of it useful.

Respond with ONLY a JSON object of the form:
{"faithfulness": <float>, "answer_relevancy": <float>, "context_precision": <float>}"""


@dataclass
class EvalScores:
    faithfulness: float
    answer_relevancy: float
    context_precision: float
    prompt_tokens: int
    completion_tokens: int

    def to_dict(self) -> dict:
        return {
            "faithfulness": self.faithfulness,
            "answer_relevancy": self.answer_relevancy,
            "context_precision": self.context_precision,
        }


def evaluate(question: str, context_chunks: list[str], answer: str) -> EvalScores:
    context_text = "\n\n".join(context_chunks) if context_chunks else "(no context retrieved)"
    user_content = (
        f"Question: {question}\n\nContext:\n{context_text}\n\nAnswer:\n{answer}"
    )
    result = chat_completion(
        [
            {"role": "system", "content": EVAL_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        model=EVAL_MODEL,
        max_tokens=150,
        temperature=0.0,
    )

    try:
        raw = result.content.strip()
        if raw.startswith("```"):
            raw = raw.strip("`").split("\n", 1)[-1]
        scores = json.loads(raw)
        faithfulness = float(scores.get("faithfulness", 0.0))
        answer_relevancy = float(scores.get("answer_relevancy", 0.0))
        context_precision = float(scores.get("context_precision", 0.0))
    except (json.JSONDecodeError, ValueError, TypeError):
        # Judge call succeeded but didn't return parseable JSON — surface
        # zeros rather than crashing the query response.
        faithfulness = answer_relevancy = context_precision = 0.0

    return EvalScores(
        faithfulness=faithfulness,
        answer_relevancy=answer_relevancy,
        context_precision=context_precision,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
    )
