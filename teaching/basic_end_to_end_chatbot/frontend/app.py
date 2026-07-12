"""Streamlit frontend for the basic end-to-end chatbot teaching demo.

Sidebar: pick a provider and optionally paste an API key. Leaving both
blank defaults to OpenAI using the key in the backend's .env file
(Feature 3). Chat history is kept per session_id so multi-turn
conversation works (Feature 4), with the actual history stored on the
FastAPI backend.
"""
from __future__ import annotations

import uuid

import requests
import streamlit as st

BACKEND_URL = "http://localhost:8000"

st.set_page_config(page_title="Basic End-to-End Chatbot", page_icon="💬")
st.title("💬 Basic End-to-End Chatbot")

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    st.header("Provider settings")
    provider = st.selectbox(
        "LLM provider",
        options=["(default: OpenAI from .env)", "openai", "anthropic", "groq", "gemini"],
        index=0,
    )
    api_key = st.text_input("API key (optional)", type="password")

    st.caption(
        "Leave provider at default and API key blank to use the OpenAI key "
        "already configured in the backend's .env file."
    )

    if st.button("Reset conversation"):
        requests.post(f"{BACKEND_URL}/reset/{st.session_state.session_id}")
        st.session_state.messages = []
        st.session_state.session_id = str(uuid.uuid4())
        st.rerun()

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

user_input = st.chat_input("Type a message...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    chosen_provider = None if provider.startswith("(default") else provider
    chosen_key = api_key.strip() or None

    payload = {
        "session_id": st.session_state.session_id,
        "message": user_input,
        "provider": chosen_provider,
        "api_key": chosen_key,
    }

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                resp = requests.post(f"{BACKEND_URL}/chat", json=payload, timeout=60)
                resp.raise_for_status()
                data = resp.json()
                reply = data["reply"]
                st.markdown(reply)
                st.caption(f"provider used: {data['provider_used']}")
            except requests.exceptions.HTTPError as e:
                reply = f"Error: {e.response.json().get('detail', str(e))}"
                st.error(reply)
            except requests.exceptions.RequestException as e:
                reply = f"Error: could not reach backend ({e})"
                st.error(reply)

    st.session_state.messages.append({"role": "assistant", "content": reply})
