"""FastAPI app entrypoint for the stock-research-debate-assistant backend.

Run with:
    uvicorn backend.main:app --reload --port 8000

All agent/graph logic lives in `backend.agent` (built by agent-builder) and
is imported here only through its public `run_turn` entrypoint — see
`backend/api/routes.py`. No mock mode: every `/chat` call goes through a
real LLM/tool pipeline; a missing/broken provider key surfaces as a real
error from `backend.agent`, not a fallback response.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import router

app = FastAPI(
    title="Stock Research & Debate Assistant API",
    description=(
        "Backend for a bull/bear/risk debate + judge synthesis agent over "
        "live stock price/fundamentals/news data. Not financial advice."
    ),
    version="0.1.0",
)

# Permissive localhost CORS for the Streamlit dev frontend (typically
# localhost:8501). This is a teaching demo, not a production deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8501",
        "http://127.0.0.1:8501",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
