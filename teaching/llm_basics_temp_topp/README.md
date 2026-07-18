# LLM Basics: Temperature, Top-p, Top-k, and Prompting

Progressive Jupyter notebook teaching LLM sampling controls and prompting basics using real Anthropic Claude calls.

## Setup

From the repo root:

```bash
cd teaching/llm_basics_temp_topp
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Add `ANTHROPIC_API_KEY` to the repo-root `.env` file or export it in your shell. The notebook also honors `ANTHROPIC_MODEL`; if unset, it uses `claude-sonnet-4-6`.

## Run

```bash
cd teaching/llm_basics_temp_topp
.venv/bin/jupyter notebook notebook.ipynb
```

## Verified

Verified on 2026-07-18 by executing `notebook.ipynb` top to bottom with:

- Provider: Anthropic Claude
- Model: `claude-sonnet-4-6`
- Vector store: none
- Observability: none
- Output artifact: `executed_notebook.ipynb`

Verification command:

```bash
teaching/llm_basics_temp_topp/.venv/bin/jupyter nbconvert --to notebook --execute teaching/llm_basics_temp_topp/notebook.ipynb --output executed_notebook.ipynb --output-dir teaching/llm_basics_temp_topp --ExecutePreprocessor.timeout=300
```
