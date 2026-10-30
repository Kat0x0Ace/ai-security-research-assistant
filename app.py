"""Streamlit chat UI for the AI Security Research Assistant.

Run:  streamlit run app.py
"""

from __future__ import annotations

import logging
from pathlib import Path

import streamlit as st
from openai import APIConnectionError

from config import DATA_DIR
from rag import RagResult, stream_answer
from ui.knowledge_base import document_titles, source_title
from ui.render import answer_html, error_html, refusal_html, sources_html, thinking_html, user_bubble_html
from ui.sidebar import render_sidebar
from warmup import start_warmup

log = logging.getLogger(__name__)

ASSISTANT_AVATAR = ":material/smart_toy:"
EXAMPLE_QUESTIONS = [
    "What is indirect prompt injection?",
    "How do multi-turn jailbreaks work?",
    "What is MITRE ATLAS?",
    "How should a RAG system treat retrieved content?",
]

st.set_page_config(page_title="AI Security Research Assistant", page_icon=":material/shield_lock:", layout="centered")
st.markdown(f"<style>{(Path(__file__).parent / 'ui' / 'styles.css').read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)

start_warmup()  # load the embedding model + LLM in the background so the first question is fast

if "messages" not in st.session_state:
    st.session_state.messages = []

titles = document_titles(DATA_DIR)
render_sidebar(titles)


def ask(question: str) -> None:
    st.session_state.pending_question = question


def to_message(result: RagResult) -> dict:
    """Store just what's needed to redraw an assistant turn on later reruns."""
    kind = "small_talk" if result.small_talk else "refusal" if result.refused else "answer"
    sources = [
        {"title": source_title(s.source, titles), "text": s.text, "distance": s.distance}
        for s in result.sources
    ] if kind == "answer" else []
    return {"role": "assistant", "kind": kind, "content": result.answer, "sources": sources}


def stream_reply(question: str) -> dict:
    """Show the assistant's reply as it's generated; return it for the history."""
    with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
        body = st.empty()
        try:
            with st.spinner("Searching the knowledge base…"):
                result, pieces = stream_answer(question)
            if pieces is not None:
                body.markdown(thinking_html(len(result.sources)), unsafe_allow_html=True)
                text = ""
                for piece in pieces:
                    text += piece
                    body.markdown(answer_html(text), unsafe_allow_html=True)
            message = to_message(result)
        except APIConnectionError:
            log.exception("Ollama unreachable")
            message = _error("I can't reach Ollama. Make sure the Ollama app is running, then ask again.")
        except Exception:
            log.exception("Answering failed")
            message = _error("I couldn't answer that because of an internal error. Check the terminal for details.")
        with body.container():  # swap the live text for the final version (+ sources)
            render_assistant_body(message)
    return message


def _error(text: str) -> dict:
    return {"role": "assistant", "kind": "error", "content": text, "sources": []}


def render_assistant_body(message: dict) -> None:
    kind = message["kind"]
    if kind == "refusal":
        st.markdown(refusal_html(), unsafe_allow_html=True)
    elif kind == "error":
        st.markdown(error_html(message["content"]), unsafe_allow_html=True)
    else:
        st.markdown(answer_html(message["content"]), unsafe_allow_html=True)
    if message["sources"]:
        with st.expander(f"{len(message['sources'])} sources"):
            st.markdown(sources_html(message["sources"]), unsafe_allow_html=True)


def render(message: dict) -> None:
    if message["role"] == "user":
        st.markdown(user_bubble_html(message["content"]), unsafe_allow_html=True)
        return
    with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
        render_assistant_body(message)


# ---------- Header ----------
st.markdown(
    '<div class="app-title rise">AI Security <em>Research</em> Assistant</div>'
    '<p class="app-lede rise d2">Ask about <strong>prompt injection, jailbreaks, RAG poisoning, '
    "the OWASP LLM Top 10 and MITRE ATLAS</strong>. Every answer points to the document it came from. "
    "If something isn't in the knowledge base, I'll say so.</p>"
    '<div class="app-rule"></div>',
    unsafe_allow_html=True,
)

prompt = st.chat_input("Ask about AI security…") or st.session_state.pop("pending_question", None)

# ---------- Empty state ----------
if not st.session_state.messages and not prompt:
    st.markdown('<div class="eyebrow rise d3" style="margin-bottom:12px">Try asking</div>', unsafe_allow_html=True)
    with st.container(key="try-asking"):
        cols = st.columns(2)
        for i, question in enumerate(EXAMPLE_QUESTIONS):
            cols[i % 2].button(f"{question}  →", key=f"example-{i}", on_click=ask, args=(question,), width="stretch")

# ---------- Conversation ----------
for message in st.session_state.messages:
    render(message)

if prompt:
    user_message = {"role": "user", "content": prompt}
    st.session_state.messages.append(user_message)
    render(user_message)
    st.session_state.messages.append(stream_reply(prompt))
