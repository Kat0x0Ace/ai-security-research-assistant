"""Hybrid retrieval: vector search fused with BM25 keyword search (RRF).

Why both (the interview answer): embeddings find *meaning* — a question about
"LLMs falling for hidden instructions" retrieves a passage that never uses
those words. But they blur exact terms: a question with "poison" in it may
rank a semantically-adjacent passage above the one that literally discusses
poisoning. BM25 is the opposite — precise on rare keywords, blind to
paraphrase. Fusing the two rankings with Reciprocal Rank Fusion (RRF) takes
the union of both strengths; neither alone wins every case.

Fusion is rank-based (RRF, k=60), so the two scorers' incomparable scales
(cosine distance vs. BM25 scores) never need calibrating.

Everything runs locally: the BM25 index is built from the chunk texts already
in ChromaDB, cached in-process, and invalidated when the collection size
changes (re-ingest). No extra infrastructure, no API.
"""

from __future__ import annotations

import os
import re
import threading

from config import LLM_TOP_K, get_collection
from ingest.embedder import embed_query

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    """Lowercase word tokens — same tokenizer builds the index and the query."""
    return _TOKEN_RE.findall(text.lower())


def hybrid_enabled() -> bool:
    return os.environ.get("HYBRID_SEARCH", "1").strip().lower() not in ("0", "false", "no")


# --- BM25 index (lazy, process-local) ---

_bm25 = None
_bm25_ids: list[str] = []
_bm25_count = -1
_lock = threading.Lock()


def get_bm25():
    """Lazy BM25 index over every chunk in the collection.

    Rebuilt when ChromaDB's collection size changes (re-ingest, prune).
    Returns (bm25, ids) or (None, []) for an empty collection.
    """
    global _bm25, _bm25_ids, _bm25_count
    collection = get_collection()
    count = collection.count()
    if count == 0:
        return None, []
    with _lock:
        if _bm25 is None or _bm25_count != count:
            from rank_bm25 import BM25Okapi

            data = collection.get(include=["documents"])
            _bm25_ids = list(data["ids"])
            corpus = [tokenize(doc) for doc in data["documents"]]
            # BM25Okapi requires a non-empty corpus with non-empty docs;
            # guard the degenerate all-empty case.
            if not corpus or not any(corpus):
                return None, []
            _bm25 = BM25Okapi(corpus)
            _bm25_count = count
    return _bm25, _bm25_ids


def invalidate_bm25() -> None:
    """Force a rebuild on next use (call after ingest/prune in-process)."""
    global _bm25, _bm25_count
    with _lock:
        _bm25 = None
        _bm25_count = -1


def rrf_fuse(*ranked_id_lists: list[str], k: int = 60) -> list[str]:
    """Reciprocal Rank Fusion over ranked id lists. k=60 is the standard constant."""
    scores: dict[str, float] = {}
    for ids in ranked_id_lists:
        for rank, cid in enumerate(ids, start=1):
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank)
    return [cid for cid, _ in sorted(scores.items(), key=lambda kv: -kv[1])]


def retrieve_hybrid(query: str, top_k: int = LLM_TOP_K) -> list[dict]:
    """Fused retrieval. Returns dicts of {id, text, source, distance}, best first.

    `distance` is the true cosine distance between the query and the stored
    chunk vector — computed for every candidate, including BM25-only ones, so
    the refusal gate in rag.py keeps exactly its old semantics.
    """
    import numpy as np

    collection = get_collection()
    if collection.count() == 0:
        return []

    vector = embed_query(query)
    # Over-fetch on both sides so fusion has something to merge.
    n_fetch = max(top_k * 2, 6)
    vec = collection.query(query_embeddings=[vector], n_results=min(n_fetch, collection.count()))
    vec_ids = list(vec["ids"][0])
    vec_meta = {cid: (doc, meta, dist) for cid, doc, meta, dist in zip(
        vec["ids"][0], vec["documents"][0], vec["metadatas"][0], vec["distances"][0])}

    bm25, bm25_ids = get_bm25()
    bm25_ranked: list[str] = []
    if bm25 is not None:
        scores = bm25.get_scores(tokenize(query))
        ranked = sorted(zip(bm25_ids, scores), key=lambda kv: -kv[1])[:n_fetch]
        bm25_ranked = [cid for cid, s in ranked if s > 0]

    fused_ids = rrf_fuse(vec_ids, bm25_ranked)[:top_k]

    # Distances: reuse the vector search's where possible; fetch stored
    # embeddings for BM25-only chunks so the refusal gate sees true distances.
    need_vectors = [cid for cid in fused_ids if cid not in vec_meta]
    stored: dict[str, tuple[str, dict, list[float]]] = {}
    if need_vectors:
        # collection.get returns a dict of parallel lists — read fields by key.
        got = collection.get(ids=need_vectors, include=["documents", "metadatas", "embeddings"])
        stored = {
            cid: (doc, meta, list(emb))
            for cid, doc, meta, emb in zip(got["ids"], got["documents"], got["metadatas"], got["embeddings"])
        }

    qv = np.asarray(vector, dtype=float)
    out = []
    for cid in fused_ids:
        if cid in vec_meta:
            doc, meta, dist = vec_meta[cid]
        elif cid in stored:
            doc, meta, emb = stored[cid]
            sv = np.asarray(emb, dtype=float)
            denom = float(np.linalg.norm(qv) * np.linalg.norm(sv))
            dist = float(1.0 - (float(np.dot(qv, sv)) / denom if denom else 0.0))
        else:
            continue
        out.append({"id": cid, "text": doc, "source": meta["source"], "distance": dist})
    return out
