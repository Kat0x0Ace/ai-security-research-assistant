"""Local embedding wrapper (sentence-transformers).

The only place in the codebase that computes embeddings. Centralizes model
loading, dimension handling, and normalization so the rest of the pipeline
doesn't need to think about it.

v2 notes:
  - Runs fully local — no API, no keys, nothing leaves the machine.
  - Sentence-transformers has no document/query task types; both paths use the
    same encoder, but we keep the task_type parameter so the SQLite cache keys
    stay forward-compatible if a bidirectional model is swapped in later.
  - Multimodal embedding (images/video) is a parked stretch goal; file inputs
    raise NotImplementedError until then.
"""

from __future__ import annotations

from pathlib import Path

from config import get_embedding_model


def embed_text(text: str, task_type: str = "document") -> list[float]:
    """Embed a single text string. Returns a normalized vector of length EMBEDDING_DIM."""
    model = get_embedding_model()
    vector = model.encode(text, normalize_embeddings=True)
    return vector.tolist()


def embed_query(text: str) -> list[float]:
    """Convenience for the search path."""
    return embed_text(text, task_type="query")


def embed_file(
    path: str | Path,
    mime_type: str = "",
    task_type: str = "document",
) -> list[float]:
    """Embed a non-text file. Parked until multimodal support (v2 stretch goal)."""
    raise NotImplementedError(
        "Multimodal embedding is parked for the v2 stretch goals. "
        "Text ingestion is fully supported via embed_text()."
    )
