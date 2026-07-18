from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import nbformat as nbf


ROOT = Path(__file__).resolve().parent


def md(text: str):
    return nbf.v4.new_markdown_cell(dedent(text).strip())


def code(text: str):
    return nbf.v4.new_code_cell(dedent(text).strip())


cells = [
    md(
        """
        # LLM Sampling and Prompting Basics: Temperature, Top-p, Top-k, and Prompt Design

        This notebook is a live teaching demo. It starts with the probability mechanics behind token sampling, then uses real Anthropic Claude calls to show how sampling controls and prompting choices change model behavior.

        Run the notebook from top to bottom. It expects `ANTHROPIC_API_KEY` in the repo-root `.env` file or in your shell environment.
        """
    ),
    md(
        """
        ## 1. Setup

        The API key is loaded from the root `.env` file when present. There is no mock mode: if the key is missing or invalid, the notebook should fail loudly because the point of this demo is to observe real model behavior.
        """
    ),
    code(
        """
        from __future__ import annotations

        import math
        import os
        import random
        from pathlib import Path

        import anthropic
        import matplotlib.pyplot as plt
        import numpy as np
        import pandas as pd
        from dotenv import load_dotenv

        # Find and load the repo-root .env even when the notebook runs from teaching/<slug>/.
        current = Path.cwd().resolve()
        for candidate in [current, *current.parents]:
            env_path = candidate / ".env"
            if env_path.exists():
                load_dotenv(env_path)
                print(f"Loaded environment from: {env_path}")
                break
        else:
            load_dotenv()
            print("No .env file found in parent folders; using shell environment only.")

        ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
        MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")

        if not ANTHROPIC_API_KEY:
            raise RuntimeError("ANTHROPIC_API_KEY is required in .env or shell environment.")

        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        print(f"Using Anthropic model: {MODEL}")
        """
    ),
    code(
        """
        def call_claude(
            prompt: str,
            *,
            system: str | None = None,
            temperature: float | None = None,
            top_p: float | None = None,
            top_k: int | None = None,
            max_tokens: int = 180,
        ) -> str:
            kwargs = {
                "model": MODEL,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            }
            if system is not None:
                kwargs["system"] = system
            if temperature is not None:
                kwargs["temperature"] = temperature
            if top_p is not None:
                kwargs["top_p"] = top_p
            if top_k is not None:
                kwargs["top_k"] = top_k

            response = client.messages.create(**kwargs)
            return response.content[0].text.strip()


        def run_variants(prompt: str, variants: list[dict], *, system: str | None = None, max_tokens: int = 160) -> pd.DataFrame:
            rows = []
            for params in variants:
                label = ", ".join(f"{k}={v}" for k, v in params.items())
                answer = call_claude(prompt, system=system, max_tokens=max_tokens, **params)
                rows.append({"settings": label, "output": answer})
            return pd.DataFrame(rows)


        smoke = call_claude("Reply with OK only.", temperature=0, max_tokens=8)
        print("API smoke test:", smoke)
        """
    ),
    md(
        """
        ## 2. The Probability View of Token Sampling

        An LLM produces a score, often called a logit, for many possible next tokens. Those logits are converted into probabilities with softmax:

        $$P(token_i)=\\frac{e^{logit_i}}{\\sum_j e^{logit_j}}$$

        Decoding is the policy for choosing the next token from that probability distribution. Greedy decoding picks the most likely token. Sampling draws from the distribution, which creates controlled variation.
        """
    ),
    code(
        """
        tokens = ["great", "useful", "strange", "risky", "unexpected", "boring"]
        logits = np.array([4.0, 3.2, 2.0, 1.0, 0.3, -0.5])


        def softmax(values: np.ndarray) -> np.ndarray:
            shifted = values - values.max()
            exps = np.exp(shifted)
            return exps / exps.sum()


        base_probs = softmax(logits)
        pd.DataFrame({"token": tokens, "logit": logits, "probability": base_probs}).round(4)
        """
    ),
    code(
        """
        plt.figure(figsize=(8, 3))
        plt.bar(tokens, base_probs)
        plt.title("Example next-token probability distribution")
        plt.ylabel("Probability")
        plt.xticks(rotation=20)
        plt.show()
        """
    ),
    md(
        """
        ## 3. Temperature

        Temperature changes how sharp or flat the next-token probability distribution is before sampling.

        $$P_T(token_i)=\\frac{e^{logit_i/T}}{\\sum_j e^{logit_j/T}}$$

        - Lower temperature makes high-probability tokens dominate. Output tends to be more stable and conservative.
        - Higher temperature gives lower-probability tokens more chance. Output tends to be more varied and creative.
        - Temperature does not make the model smarter; it changes how much randomness is allowed during token selection.
        """
    ),
    code(
        """
        def temperature_probs(logits: np.ndarray, temperature: float) -> np.ndarray:
            if temperature <= 0:
                probs = np.zeros_like(logits, dtype=float)
                probs[np.argmax(logits)] = 1.0
                return probs
            return softmax(logits / temperature)


        temp_table = pd.DataFrame({"token": tokens})
        for temp in [0.2, 0.7, 1.0, 1.5]:
            temp_table[f"T={temp}"] = temperature_probs(logits, temp)

        temp_table.round(4)
        """
    ),
    code(
        """
        plt.figure(figsize=(9, 4))
        x = np.arange(len(tokens))
        width = 0.2
        for i, temp in enumerate([0.2, 0.7, 1.0, 1.5]):
            plt.bar(x + i * width, temperature_probs(logits, temp), width=width, label=f"T={temp}")
        plt.xticks(x + width * 1.5, tokens, rotation=20)
        plt.ylabel("Probability")
        plt.title("Temperature reshapes the same logits")
        plt.legend()
        plt.show()
        """
    ),
    code(
        """
        temperature_prompt = (
            "Give one creative product idea for helping students learn Python. "
            "Answer in exactly two bullet points: Idea and Why it helps."
        )

        temperature_results = run_variants(
            temperature_prompt,
            [
                {"temperature": 0.0},
                {"temperature": 0.4},
                {"temperature": 0.9},
                {"temperature": 1.0},
            ],
            max_tokens=140,
        )
        temperature_results
        """
    ),
    md(
        """
        ### Why Temperature Changes the Output

        Temperature changes the model's willingness to sample from less likely continuations. With a low value, similar prompts often stay close to the safest, most probable answer. With a higher value, the model explores a wider part of the distribution, so word choice, structure, examples, and even idea selection can vary.
        """
    ),
    md(
        """
        ## 4. Top-p, or Nucleus Sampling

        Top-p keeps the smallest set of tokens whose cumulative probability reaches `p`, then samples only from that set.

        Example: if the top tokens have probabilities `[0.50, 0.25, 0.12, 0.07, 0.04, 0.02]` and `top_p=0.80`, the candidate set is roughly the first three tokens because `0.50 + 0.25 + 0.12 = 0.87`.

        Lower `top_p` narrows the candidate set. Higher `top_p` allows a broader set.
        """
    ),
    code(
        """
        def top_p_filter(probs: np.ndarray, p: float) -> pd.DataFrame:
            order = np.argsort(probs)[::-1]
            cumulative = 0.0
            keep = np.zeros_like(probs, dtype=bool)
            for idx in order:
                cumulative += probs[idx]
                keep[idx] = True
                if cumulative >= p:
                    break
            filtered = np.where(keep, probs, 0.0)
            filtered = filtered / filtered.sum()
            return pd.DataFrame({
                "token": tokens,
                "original_probability": probs,
                f"kept_by_top_p_{p}": keep,
                "renormalized_probability": filtered,
            })


        top_p_filter(base_probs, 0.80).round(4)
        """
    ),
    code(
        """
        top_p_prompt = (
            "Suggest a short analogy for explaining neural networks to a 12-year-old. "
            "Keep it under 60 words."
        )

        top_p_results = run_variants(
            top_p_prompt,
            [
                {"top_p": 0.35},
                {"top_p": 0.70},
                {"top_p": 0.95},
            ],
            max_tokens=120,
        )
        top_p_results
        """
    ),
    md(
        """
        ### Why Top-p Changes the Output

        Top-p changes the candidate pool dynamically. If the distribution is already confident, a small number of tokens may pass the threshold. If the distribution is flatter, more tokens may be included. That makes top-p different from simply choosing a fixed number of tokens.
        """
    ),
    md(
        """
        ## 5. Top-k

        Top-k keeps exactly the `k` highest-probability candidate tokens and removes the rest before sampling.

        - Small `k`: narrower, safer candidate set.
        - Large `k`: more possible continuations.
        - Unlike top-p, top-k uses a fixed count rather than a cumulative probability threshold.
        """
    ),
    code(
        """
        def top_k_filter(probs: np.ndarray, k: int) -> pd.DataFrame:
            order = np.argsort(probs)[::-1]
            keep = np.zeros_like(probs, dtype=bool)
            keep[order[:k]] = True
            filtered = np.where(keep, probs, 0.0)
            filtered = filtered / filtered.sum()
            return pd.DataFrame({
                "token": tokens,
                "original_probability": probs,
                f"kept_by_top_k_{k}": keep,
                "renormalized_probability": filtered,
            })


        top_k_filter(base_probs, 3).round(4)
        """
    ),
    code(
        """
        top_k_prompt = (
            "Invent a memorable one-sentence mnemonic for remembering what API rate limits are."
        )

        top_k_results = run_variants(
            top_k_prompt,
            [
                {"top_k": 1},
                {"top_k": 10},
                {"top_k": 50},
            ],
            max_tokens=120,
        )
        top_k_results
        """
    ),
    md(
        """
        ### Why Top-k Changes the Output

        Top-k limits how many alternatives can compete at each token position. With `top_k=1`, the model is close to greedy decoding: it repeatedly chooses from only the single best next token. With a larger `top_k`, lower-ranked tokens have room to appear, which can change phrasing and direction.
        """
    ),
    md(
        """
        ## 6. System Prompts

        A system prompt gives high-level behavioral instructions to the model. It is useful for role, tone, constraints, refusal behavior, output format, and domain expectations.

        The user prompt asks what to do. The system prompt sets the operating frame for how to do it.
        """
    ),
    code(
        """
        system_user_prompt = "Explain recursion in Python in about 80 words."

        system_results = pd.DataFrame(
            [
                {
                    "setup": "No system prompt",
                    "output": call_claude(system_user_prompt, temperature=0.4, max_tokens=140),
                },
                {
                    "setup": "System: beginner-friendly tutor",
                    "output": call_claude(
                        system_user_prompt,
                        system="You are a patient Python tutor. Use simple language and one tiny example.",
                        temperature=0.4,
                        max_tokens=160,
                    ),
                },
                {
                    "setup": "System: senior engineer",
                    "output": call_claude(
                        system_user_prompt,
                        system="You are a senior software engineer. Be precise, mention stack frames, and avoid oversimplifying.",
                        temperature=0.4,
                        max_tokens=160,
                    ),
                },
            ]
        )
        system_results
        """
    ),
    md(
        """
        ### Why the System Prompt Matters

        The same user request can produce different answers because the system prompt changes the model's objective and style constraints. It does not replace the user prompt; it guides how the user prompt is interpreted.
        """
    ),
    md(
        """
        ## 7. Zero-shot Prompting

        Zero-shot prompting gives the model an instruction without examples. It works well when the task is common or the desired format is simple.
        """
    ),
    code(
        """
        task = "Classify this customer message as positive, neutral, or negative: 'The setup was confusing, but support fixed it quickly.'"

        zero_shot = call_claude(
            task + " Return only the label and one short reason.",
            temperature=0.2,
            max_tokens=80,
        )
        print(zero_shot)
        """
    ),
    md(
        """
        ## 8. Few-shot Prompting

        Few-shot prompting includes examples so the model can infer the desired mapping, tone, or format. It is especially useful when labels are custom or when output style matters.
        """
    ),
    code(
        """
        few_shot_prompt = \"\"\"
        Classify customer messages.

        Examples:
        Message: "The dashboard loads instantly now."
        Label: positive
        Reason: The customer reports improved performance.

        Message: "I cannot find the billing page."
        Label: negative
        Reason: The customer is blocked by navigation.

        Message: "The export finished after about five minutes."
        Label: neutral
        Reason: The customer reports a factual outcome without clear sentiment.

        Now classify:
        Message: "The setup was confusing, but support fixed it quickly."
        Return Label and Reason.
        \"\"\"

        few_shot = call_claude(few_shot_prompt, temperature=0.2, max_tokens=100)
        print(few_shot)
        """
    ),
    md(
        """
        ### Why Zero-shot and Few-shot Can Differ

        In zero-shot mode, the model relies on its general understanding of the task. In few-shot mode, the examples become a local pattern: they can influence label boundaries, level of detail, output format, and how mixed sentiment is handled.
        """
    ),
    md(
        """
        ## 9. Chain-of-Thought-Style Prompting and Structured Reasoning

        Chain-of-thought prompting historically meant asking a model to show step-by-step reasoning. In production, a better pattern is usually to ask the model to reason carefully internally and return a concise explanation, checklist, or final decision. This keeps the output useful without requiring verbose hidden reasoning.
        """
    ),
    code(
        """
        reasoning_question = (
            "A laptop costs $1200. It is discounted by 15%, then sales tax of 8% is added. "
            "What is the final price?"
        )

        direct_answer = call_claude(
            reasoning_question + " Give only the final price.",
            temperature=0,
            max_tokens=80,
        )

        structured_answer = call_claude(
            reasoning_question
            + " Think through the arithmetic privately, then return: discount amount, post-discount price, tax amount, final price.",
            temperature=0,
            max_tokens=140,
        )

        pd.DataFrame(
            [
                {"prompt_style": "Direct final answer", "output": direct_answer},
                {"prompt_style": "Structured reasoning summary", "output": structured_answer},
            ]
        )
        """
    ),
    md(
        """
        ## 10. Other Key Prompting Techniques

        These techniques are often more important than tweaking sampling parameters:

        - Role prompting: assign expertise or audience.
        - Format constraints: specify JSON, bullets, table, rubric, or schema.
        - Decomposition: break a large task into smaller subtasks.
        - Delimiters: separate instructions from data.
        - Self-checking: ask for a compact validation pass against stated criteria.
        """
    ),
    code(
        """
        base_question = "Turn this vague note into a useful project task: 'make search better for users'"

        technique_prompts = [
            {
                "technique": "Role prompting",
                "prompt": base_question + "\\nYou are a product manager writing for an engineering team.",
            },
            {
                "technique": "Format constraints",
                "prompt": base_question + "\\nReturn exactly three fields: Problem, Acceptance Criteria, Out of Scope.",
            },
            {
                "technique": "Decomposition",
                "prompt": base_question + "\\nBreak the work into discovery, implementation, and validation tasks.",
            },
            {
                "technique": "Delimiters",
                "prompt": "Rewrite the note between <note> tags as a clear task.\\n<note>make search better for users</note>",
            },
            {
                "technique": "Self-checking",
                "prompt": base_question + "\\nDraft the task, then add a short 'Check' line saying whether it is measurable.",
            },
        ]

        rows = []
        for item in technique_prompts:
            rows.append(
                {
                    "technique": item["technique"],
                    "output": call_claude(item["prompt"], temperature=0.3, max_tokens=130),
                }
            )

        pd.DataFrame(rows)
        """
    ),
    md(
        """
        ## 11. Practical Guidelines

        - Use low temperature for factual, deterministic, or grading-like tasks.
        - Use higher temperature for ideation, brainstorming, and copy variation.
        - Use top-p to control how much probability mass remains available.
        - Use top-k to control the fixed number of candidate tokens.
        - Change one sampling parameter at a time when teaching or debugging.
        - Prefer clear prompts, examples, and output constraints before trying to solve quality problems with sampling settings.
        """
    ),
]


notebook = nbf.v4.new_notebook()
notebook["cells"] = cells
notebook["metadata"] = {
    "kernelspec": {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3",
    },
    "language_info": {
        "name": "python",
        "pygments_lexer": "ipython3",
    },
}

nbf.write(notebook, ROOT / "notebook.ipynb")
print(f"Wrote {ROOT / 'notebook.ipynb'}")
