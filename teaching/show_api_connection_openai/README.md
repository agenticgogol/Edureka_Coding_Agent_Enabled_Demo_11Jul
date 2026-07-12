# Show API Connection: OpenAI

A progressive teaching notebook: basic OpenAI API call → add a system prompt → print token usage/cost.

## How to run

```bash
cd teaching/show_api_connection_openai
python3 -m venv venv          # if not already created
./venv/bin/pip install -r requirements.txt
echo "OPENAI_API_KEY=sk-..." >> .env   # or set it in the repo-root .env
./venv/bin/jupyter notebook notebook.ipynb
```

Run all cells top to bottom.

## Verified against

Provider: OpenAI
Model: `gpt-4o-mini`
Verified 2026-07-12 — full notebook executed top to bottom with real API calls, all three steps produced expected output (plain answer, pirate-voice answer from the system prompt, and a token usage/cost printout).
