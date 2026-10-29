"""Streamlit chat UI for the RAG copilot.

Run:  streamlit run app.py
"""

from __future__ import annotations

import streamlit as st

from config import DATA_DIR
from ingest.pipeline import ingest_data_dir
from rag import REFUSAL_TEXT, answer

st.set_page_config(page_title="RAG Research Copilot", page_icon="🔎")
st.title("🔎 RAG Research Copilot")
st.caption(f"Answers come only from the documents in `{DATA_DIR}` — with citations, or a refusal.")

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Ask a question about your documents..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            result = answer(prompt)
        st.markdown(result.answer)
        if result.refused:
            st.info("Refused: nothing in the corpus was close enough to ground an answer.")
        elif result.sources:
            with st.expander("Sources"):
                for i, src in enumerate(result.sources, start=1):
                    st.markdown(f"**[{i}]** `{src.citation}` (distance {src.distance:.3f})")
                    st.text(src.text[:400] + ("..." if len(src.text) > 400 else ""))

    st.session_state.messages.append({"role": "assistant", "content": result.answer})

with st.sidebar:
    st.header("Corpus")
    if st.button("Re-ingest data/ folder"):
        with st.spinner("Ingesting..."):
            summary = ingest_data_dir()
        st.success(
            f"{summary['documents']} docs · {summary['chunks']} chunks in index · "
            f"{summary['embedded']} newly embedded · {summary['cache_hits']} cache hits"
        )
    st.caption(REFUSAL_TEXT)
