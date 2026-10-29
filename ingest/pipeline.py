"""Ingestion pipeline: load -> chunk -> embed (cached) -> upsert to ChromaDB.

Chunk IDs are deterministic (sha256 of source + text) so re-ingesting the
same corpus is idempotent — unchanged chunks are skipped, changed chunks
are replaced, deleted documents can be pruned.
"""

from __future__ import annotations

import hashlib

from config import DATA_DIR, get_collection
from ingest.cache import get as cache_get, put as cache_put
from ingest.chunker import chunk_text
from ingest.embedder import embed_text
from ingest.loader import load_data_dir


def _chunk_id(source: str, chunk_index: int, text: str) -> str:
    h = hashlib.sha256()
    h.update(source.encode())
    h.update(b"|")
    h.update(str(chunk_index).encode())
    h.update(b"|")
    h.update(text.encode())
    return h.hexdigest()


def ingest_data_dir(data_dir=DATA_DIR, batch_size: int = 32) -> dict:
    """Ingest every supported document in data_dir. Returns a summary dict."""
    pairs = load_data_dir(data_dir)
    if not pairs:
        return {"documents": 0, "chunks": 0, "embedded": 0, "cache_hits": 0}

    collection = get_collection()
    existing_ids = set(collection.get(include=[])["ids"])

    documents: list[str] = []
    metadatas: list[dict] = []
    ids: list[str] = []
    embeddings: list[list[float]] = []
    embedded = 0
    cache_hits = 0

    def flush():
        nonlocal documents, metadatas, ids, embeddings
        if documents:
            collection.upsert(
                ids=ids,
                documents=documents,
                metadatas=metadatas,
                embeddings=embeddings or None,
            )
            documents, metadatas, ids, embeddings = [], [], [], []

    for source, text in pairs:
        for i, chunk in enumerate(chunk_text(text)):
            cid = _chunk_id(source, i, chunk)
            if cid in existing_ids:
                continue  # unchanged chunk — skip entirely
            content = chunk.encode("utf-8")
            cached = cache_get(content, "document")
            if cached is None:
                vector = embed_text(chunk, task_type="document")
                cache_put(content, "document", vector)
                embedded += 1
            else:
                vector = cached
                cache_hits += 1
            documents.append(chunk)
            metadatas.append({"source": source, "chunk_index": i})
            ids.append(cid)
            embeddings.append(vector)
            if len(ids) >= batch_size:
                flush()

    flush()
    return {
        "documents": len(pairs),
        "chunks": collection.count(),
        "embedded": embedded,
        "cache_hits": cache_hits,
    }


def prune_stale(data_dir=DATA_DIR) -> int:
    """Remove chunks whose source no longer exists in data_dir. Returns pruned count."""
    collection = get_collection()
    live_sources = {name for name, _ in load_data_dir(data_dir)}
    stale_ids = [
        cid
        for cid, meta in zip(
            collection.get(include=["metadatas"])["ids"],
            collection.get(include=["metadatas"])["metadatas"],
        )
        if meta["source"] not in live_sources
    ]
    if stale_ids:
        collection.delete(ids=stale_ids)
    return len(stale_ids)
