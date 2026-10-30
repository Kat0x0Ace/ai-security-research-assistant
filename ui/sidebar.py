"""Sidebar: what the assistant knows (document index) + rebuild button."""

from __future__ import annotations

import html
import logging

import streamlit as st

from config import OLLAMA_MODEL, get_collection
from ingest.pipeline import ingest_data_dir

log = logging.getLogger(__name__)


def render_sidebar(titles: dict[str, str]) -> None:
    with st.sidebar:
        passages = _passage_count()
        passages_text = f"<b>{passages}</b> passages" if passages is not None else "index unavailable"
        st.markdown(
            '<div class="eyebrow">Knowledge base</div>'
            '<div class="kb-title">What I know</div>'
            f'<div class="kb-stats"><b>{len(titles)}</b> documents · {passages_text}</div>',
            unsafe_allow_html=True,
        )

        if titles:
            items = "".join(f"<li>{html.escape(t)}</li>" for t in sorted(titles.values(), key=str.lower))
            st.markdown(f'<ul class="kb-index">{items}</ul>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="kb-empty">No documents yet. Add .md, .txt or .pdf files to the data folder.</div>', unsafe_allow_html=True)

        with st.container(key="rebuild"):
            if st.button("↻  Rebuild knowledge base", width="stretch"):
                _rebuild()
        st.markdown('<div class="kb-hint">Added or changed files in data/? Rebuild to include them.</div>', unsafe_allow_html=True)

        notice = st.session_state.pop("rebuild_notice", None)
        if notice:
            (st.success if notice[0] == "ok" else st.error)(notice[1])

        st.markdown(
            '<div class="kb-local"><span class="dot"></span>Running locally · nothing leaves this machine</div>'
            f'<div class="kb-model">Model <b>{html.escape(OLLAMA_MODEL)}</b> via Ollama</div>',
            unsafe_allow_html=True,
        )


def _passage_count() -> int | None:
    try:
        return get_collection().count()
    except Exception:
        log.exception("Could not read the vector index")
        return None


def _rebuild() -> None:
    with st.spinner("Rebuilding knowledge base…"):
        try:
            summary = ingest_data_dir()
            st.session_state.rebuild_notice = (
                "ok",
                f"Done: {summary['documents']} documents, {summary['chunks']} passages "
                f"({summary['embedded']} new, {summary['cache_hits']} unchanged).",
            )
        except Exception:
            log.exception("Rebuild failed")
            st.session_state.rebuild_notice = ("error", "Rebuild failed. Check the terminal for details.")
    st.rerun()  # refresh the counts above
