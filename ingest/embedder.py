"""Gemini Embedding 2 wrapper.

The only place in the codebase that calls the Gemini embeddings API.
Centralizes retry logic, dimension handling, and task-type selection so the
rest of the pipeline doesn't need to think about it.

Task types (from Gemini docs):
  - RETRIEVAL_DOCUMENT  : for content being indexed
  - RETRIEVAL_QUERY     : for the user's question at query time
  - SEMANTIC_SIMILARITY : for symmetric similarity comparisons
"""

from __future__ import annotations

import random
import time
from pathlib import Path
from typing import Literal

from google.genai import types

from config import EMBEDDING_DIM, EMBEDDING_MODEL, get_gemini_client

TaskType = Literal["RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY", "SEMANTIC_SIMILARITY"]

_MAX_RETRIES = 3
_BASE_BACKOFF = 1.5  # seconds


def _retry(fn, *args, **kwargs):
    """Call fn with exponential backoff + jitter on transient failures."""
    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 — SDK raises a wide variety
            last_exc = exc
            if attempt == _MAX_RETRIES - 1:
                break
            sleep = _BASE_BACKOFF * (2**attempt) + random.uniform(0, 0.5)
            print(
                f"[embedder] attempt {attempt + 1}/{_MAX_RETRIES} failed "
                f"({type(exc).__name__}): {exc}. Retrying in {sleep:.1f}s..."
            )
            time.sleep(sleep)
    assert last_exc is not None
    raise last_exc


def _config(task_type: TaskType) -> types.EmbedContentConfig:
    return types.EmbedContentConfig(
        task_type=task_type,
        output_dimensionality=EMBEDDING_DIM,
    )


def embed_text(text: str, task_type: TaskType = "RETRIEVAL_DOCUMENT") -> list[float]:
    """Embed a single text string. Returns a vector of length EMBEDDING_DIM."""
    client = get_gemini_client()

    def _call():
        result = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=text,
            config=_config(task_type),
        )
        return list(result.embeddings[0].values)

    return _retry(_call)


def embed_query(text: str) -> list[float]:
    """Convenience for the search path."""
    return embed_text(text, task_type="RETRIEVAL_QUERY")


def embed_file(
    path: str | Path,
    mime_type: str,
    task_type: TaskType = "RETRIEVAL_DOCUMENT",
) -> list[float]:
    """Embed a single image / video / audio / pdf file.

    Caller is responsible for ensuring the file meets Gemini's size limits:
      - image: ≤6 per request, PNG/JPEG
      - video: ≤120s, MP4/MOV
      - audio: ≤180s, MP3/WAV
      - pdf:   ≤6 pages
    """
    path = Path(path)
    client = get_gemini_client()

    def _call():
        with path.open("rb") as f:
            blob = types.Part.from_bytes(data=f.read(), mime_type=mime_type)
        result = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=blob,
            config=_config(task_type),
        )
        return list(result.embeddings[0].values)

    return _retry(_call)
