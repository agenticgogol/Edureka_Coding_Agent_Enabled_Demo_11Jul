# Stock Research & Debate Assistant

Full-app teaching demo: a Streamlit frontend calls a FastAPI backend that
routes each question, fetches live yfinance data (and Tavily/Frankfurter MCP
data when needed), runs a bounded bull/bear/risk debate, and produces a
Buy/Sell/Hold judge synthesis. The UI keeps the reasoning trail expanded and
renders price, fundamentals, and comparison visuals. It is educational only,
not financial advice.

## Run locally

The one-command launcher handles virtualenv creation, dependency installation,
backend startup/health checking, frontend startup, and cleanup:

```bash
./run.sh
```

Use `BACKEND_PORT=8001 FRONTEND_PORT=8502 ./run.sh` to override the default
ports.

From this directory, create and activate a virtual environment, then install
both requirement files:

```bash
python3.12 -m venv .venv-3.12
source .venv-3.12/bin/activate
pip install -r backend/requirements.txt
pip install -r frontend/requirements.txt
```

Configure the real keys in the repository `.env` (or export them):

```bash
ANTHROPIC_API_KEY=...
TAVILY_API_KEY=...
```

Start the backend in one terminal:

```bash
source .venv-3.12/bin/activate
uvicorn backend.main:app --reload --port 8000
```

Start the frontend in a second terminal:

```bash
source .venv-3.12/bin/activate
BACKEND_URL=http://localhost:8000 streamlit run app.py
```

The sidebar lets the user choose provider/model and optionally override the
provider key for the session. There is no mock or fallback response path.
Phoenix tracing is enabled when configured/available; otherwise the backend
writes structured spans to `backend/data/trace_log.jsonl`.

## Approved verification flow

1. Ask about AAPL with a stated moderate risk tolerance.
2. Ask why the bear agent said its point; this reuses the transcript without
   fetching new market data.
3. Ask whether MSFT is overvalued based on P/E; the trail shows news skipped.
4. Compare TCS.NS and INFY.NS for a conservative investor; comparison bars
   and cross-currency handling appear when required.
5. Start a fresh session with the same user key; the sidebar surfaces stored
   risk tolerance and relevant prior ticker analysis.

All live calls require the configured real provider and Tavily credentials.

## Milestone 2 allocation output

Enable **Allocation mode** in the sidebar or ask a natural-language question
such as:

```text
I have $100,000 to invest across AAPL, MSFT, and JNJ. How should I split it?
```

The result includes each ticker's percentage and currency amount, overall
historical annualized return, historical annualized volatility, equal-weight
return/volatility, per-asset risk contribution, sector concentration, and the
optimizer's deterministic allocation reasoning. These figures use historical
prices through the displayed date; they are not forecasts or guarantees.

## Cost controls

The default LLM output budget is capped at 1024 tokens per call. Override it
with `LLM_MAX_OUTPUT_TOKENS` when teaching a larger response. Allocation
turns use one bull/bear/risk opening round because all weights and metrics are
already computed deterministically; the original two-round stock debate is
unchanged. Allocation questions also send only compact summaries to the LLM,
while the full historical series remains local to the optimizer.
