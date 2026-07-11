"""Minimal DSPy sketch — Signature + Module + optional optimizer.

TREAT AS A STARTING SKETCH, NOT GROUND TRUTH. DSPy's API has changed
significantly across versions (dspy.OpenAI vs dspy.LM, teleprompter names,
etc.) — always research-first against currently installed version's docs
before trusting this file verbatim. Install: pip install dspy-ai (or dspy,
check current package name).
"""
from __future__ import annotations

import dspy


class AnswerQuestion(dspy.Signature):
    """Answer a question concisely and factually."""

    question: str = dspy.InputField()
    answer: str = dspy.OutputField(desc="A concise, factual answer, 1-2 sentences")


class QAProgram(dspy.Module):
    def __init__(self):
        super().__init__()
        self.answer = dspy.ChainOfThought(AnswerQuestion)

    def forward(self, question: str):
        return self.answer(question=question)


def configure_lm(api_key: str, provider: str = "anthropic") -> None:
    """Raises if api_key is empty — no mock mode. Caller (config.py's
    require_llm_key()) should already have verified a key exists before
    this is ever called."""
    if not api_key:
        raise RuntimeError("No LLM API key configured — this repo has no mock mode.")
    # Adjust to whatever DSPy's current LM configuration API is at install
    # time — this is exactly the kind of call to verify via research-first.
    lm = dspy.LM(f"{provider}/claude-sonnet-5", api_key=api_key)
    dspy.configure(lm=lm)


def run_program(question: str, api_key: str) -> str:
    """Entrypoint the backend calls. api_key must be a real, verified key."""
    configure_lm(api_key)
    program = QAProgram()
    result = program(question=question)
    return result.answer


if __name__ == "__main__":
    import os

    key = os.environ.get("ANTHROPIC_API_KEY", "")
    print(run_program("What is retrieval-augmented generation?", api_key=key))
