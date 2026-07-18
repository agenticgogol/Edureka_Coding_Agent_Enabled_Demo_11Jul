# Teaching Brief: LLM Basics Temperature, Top-p, Top-k, and Prompting

## Description (as given by user)
Create a Jupyter notebook with the following agenda:

- Explain what temperature is in markdown.
- Use code cells to show how different temperature values affect output for the same question.
- Explain why the changes happen.
- Explain what top-p is in markdown.
- Use code cells to show and explain how different top-p values change output.
- Explain why and what is happening.
- Explain what top-k is in markdown.
- Use code cells to show and explain how different top-k values change output.
- Explain why and what is happening.
- Explain what a system prompt is.
- Show with code how output differs with and without a system prompt.
- Explain zero-shot prompting.
- Explain few-shot prompting.
- Show how output differs for the same question with examples and code.
- Explain chain-of-thought prompting with examples.
- Include other key prompting techniques with examples and markdown explanations.

Make the notebook solid and useful for a beginner-to-intermediate-to-advanced audience, including probability and sampling math.

## Steps (in order, each builds on the previous)
a) Sampling basics: temperature, probability distributions, and why repeated calls can differ -- added 2026-07-18.
b) Temperature experiments: run the same prompt with low, medium, and high temperatures -- added 2026-07-18.
c) Top-p explanation and experiments: compare constrained vs broader nucleus sampling -- added 2026-07-18.
d) Top-k explanation and experiments: compare small vs larger candidate-token pools using Anthropic Claude's `top_k` parameter -- added 2026-07-18.
e) System prompt experiments: compare the same user question with no system prompt and with targeted system prompts -- added 2026-07-18.
f) Prompting techniques: zero-shot, few-shot, chain-of-thought-style structured reasoning, role prompting, format constraints, decomposition, and self-check prompts -- added 2026-07-18.

## Format
notebook

## Happy-path test case (user-approved)
A learner opens the notebook, uses `ANTHROPIC_API_KEY` from the root `.env` or shell environment, runs the cells from top to bottom, and sees live Claude responses demonstrating how temperature, top-p, top-k, system prompts, and prompting strategies change answers for the same or closely related questions.

## Observability
none

## Vector store
none

## Constraints
- Use Anthropic Claude for real API calls because `claude-sonnet-4-6` supports `temperature`, `top_p`, and `top_k` when varied independently.
- Require `ANTHROPIC_API_KEY` in `.env`.
- No mock mode or canned fallback responses.
- Keep explanations accessible to beginners while adding probability and sampling math for advanced learners.
- Build as a Jupyter notebook.

## Audience level
beginner to intermediate to advanced

## Decisions
- Provider: Anthropic Claude.
- Verified model: `claude-sonnet-4-6` with real Anthropic calls for `temperature`, `top_p`, and `top_k` on 2026-07-18.
- Observability: none.
- Vector store: none, because this demo is about sampling and prompting rather than retrieval.

## Checkpoint status
- Description: approved
- Clarifications: approved
- Format: approved
- Happy-path test case: approved
- API key verification: verified
- Observability: approved
- Vector store: approved
- Ready to generate: approved
- Build: complete
- Verify: complete
