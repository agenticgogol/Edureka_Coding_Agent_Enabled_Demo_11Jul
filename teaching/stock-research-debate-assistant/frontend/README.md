# Stock Research & Debate Assistant — Frontend

Streamlit UI for the multi-agent stock research/debate backend.

## Run

```bash
cd teaching/stock-research-debate-assistant/frontend
pip install -r requirements.txt
export BACKEND_URL=http://localhost:8000  # optional, this is the default
streamlit run app.py
```

The backend (FastAPI, under `../backend`) must be running for chat requests
to succeed. There is no mock mode — if the backend is unreachable, the app
shows a connection error rather than fabricating a response.

## Notes

- The reasoning trail is rendered as one expander per turn, each expanded
  by default and never collapsed/removed — this satisfies the brief's
  requirement that the trail stay visible after the final answer renders.
- The backend's `/chat` contract returns the full trail only after the
  pipeline completes (no incremental streaming), so the "live" fill-in
  effect is a cosmetic simulated reveal over already-complete data (see the
  docstring in `app.py`).
- The backend sends the complete yfinance payload in the price trail event,
  including `price_history`, and emits a `fundamentals_comparison` event
  after parallel ticker fetches join. The rendering helpers use those
  documented shapes for stat cards, the price trend, and comparison bars.
- Large values are displayed compactly in cards using `K`, `Mn`, `Bn`, and
  `Tn` suffixes. Each completed turn also shows a progress bar and a compact
  stage summary before the expanded reasoning details.
- Allocation mode adds structured ticker, amount, currency, and optional
  target-return controls; natural-language allocation questions remain
  supported as well.
- Chat requests use a backend job endpoint and poll real graph progress events
  while the request runs. The completed response stores the same trail in the
  turn expander, so progress remains visible after the answer arrives.
