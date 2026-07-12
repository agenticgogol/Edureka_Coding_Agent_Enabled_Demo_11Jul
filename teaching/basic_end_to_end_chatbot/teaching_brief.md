# Teaching Brief: Basic End-to-End Chatbot

## Description (as given by user)
Develop a basic chatbot:
- Frontend: Streamlit
- API layer: FastAPI
- Backend: LLM / Agent

Feature 1: The frontend should allow choosing LLM provider and API.
Feature 2: User can enter the API key in the frontend as well.
Feature 3: If user does not choose LLM provider or API key, default to OpenAI. The OpenAI key is available in the `.env` file.
Feature 4: Chatbot stores session history — supports multi-turn conversation.

## Steps (in order, each builds on the previous)
a) Streamlit sidebar: provider dropdown (OpenAI/Anthropic/Groq/Gemini) + optional API key input — added 2026-07-13
b) FastAPI backend endpoint that accepts provider, optional api_key, session_id, and message — added 2026-07-13
c) Default-to-OpenAI-from-.env logic when provider/key not chosen — added 2026-07-13
d) In-memory multi-turn session history keyed by session_id on the backend — added 2026-07-13

## Format
full_app (streamlit + fastapi)

## Happy-path test case (user-approved)
1. Default flow: User opens the Streamlit app, leaves provider/API key at default. Types "What is the capital of France?" -> app calls FastAPI, which uses the OpenAI key from `.env` (since nothing was chosen) -> returns "Paris". Follow-up "What is its population?" (no restating "Paris") gets a coherent answer, proving multi-turn memory works via session_id.
2. Explicit choice flow: User picks a provider (e.g. Anthropic) from the sidebar dropdown and pastes their own API key. Types "What is the capital of France?" -> app calls FastAPI, which uses the chosen provider + user-supplied key -> returns "Paris". Follow-up works the same way, confirming multi-turn memory persists per session regardless of which provider was used.

## Observability
none

## Vector store
none

## Constraints
- Providers supported: OpenAI (default, key from `.env` as `OPENAI_API_KEY`), Anthropic, Groq, Gemini (user supplies key via frontend for non-default providers).
- Session history stored in-memory on the FastAPI backend, keyed by `session_id`. Lost on server restart — acceptable for a live teaching demo.
- No mock mode — all calls go to real providers.

## Audience level
intermediate

## Decisions
- No vector store / RAG needed — plain chatbot only.
- No observability wiring — kept demo focused on provider-switching + multi-turn chat.

## Checkpoint status
- Description: approved
- Clarifications: approved
- Format: approved
- Happy-path test case: approved
- API key verification: verified (OpenAI, gpt-4o-mini, live call succeeded)
- Observability: approved
- Vector store: approved
- Ready to generate: approved
- Build: complete
- Verify: complete
