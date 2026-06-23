"""SQLite-backed embedding cache.

Avoids re-embedding the same content when ingestion is re-run.
Keyed by SHA256 of (model + dim + task_type + content_bytes).
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from config import CACHE_DIR, EMBEDDING_DIM, EMBEDDING_MODEL

_DB_PATH = CACHE_DIR / "embeddings.sqlite"


def _hash_key(content: bytes, task_type: str) -> str:
    h = hashlib.sha256()
    h.update(EMBEDDING_MODEL.encode())
    h.update(b"|")
    h.update(str(EMBEDDING_DIM).encode())
    h.update(b"|")
    h.update(task_type.encode())
    h.update(b"|")
    h.update(content)
    return h.hexdigest()


@contextmanager
def _conn():
    conn = sqlite3.connect(_DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


def init_cache() -> None:
    """Create the cache table if missing. Safe to call repeatedly."""
    with _conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS embeddings (
                key TEXT PRIMARY KEY,
                vector_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()


def get(content: bytes, task_type: str) -> list[float] | None:
    key = _hash_key(content, task_type)
    with _conn() as conn:
        row = conn.execute(
            "SELECT vector_json FROM embeddings WHERE key = ?", (key,)
        ).fetchone()
    if row is None:
        return None
    return json.loads(row[0])


def put(content: bytes, task_type: str, vector: list[float]) -> None:
    key = _hash_key(content, task_type)
    with _conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO embeddings (key, vector_json) VALUES (?, ?)",
            (key, json.dumps(vector)),
        )
        conn.commit()


# Initialise on import so callers can use get/put immediately.
init_cache()
