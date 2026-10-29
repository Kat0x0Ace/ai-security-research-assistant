"""Single source of truth for env vars and client singletons (v2 — local stack).

Importing this module:
  - Loads .env
  - Validates required settings
  - Returns lazy-initialized clients via get_* functions

v2 stack (free + local, nothing leaves your machine):
  - Embeddings: sentence-transformers (local model)
  - Vector DB : ChromaDB (persistent local store under cache/chroma)
  - LLM       : Ollama via its OpenAI-compatible endpoint
"""

from __future__ import annotations

import os
from functools import cache
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _get(name: str, default: str) -> str:
    return os.environ.get(name, default).strip() or default


# --- Embeddings (local) ---
EMBEDDING_MODEL = _get("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
EMBEDDING_DIM = int(_get("EMBEDDING_DIM", "384"))

# --- ChromaDB (local) ---
CHROMA_COLLECTION = _get("CHROMA_COLLECTION", "rag_agent")

# --- LLM (Ollama, OpenAI-compatible endpoint) ---
OLLAMA_BASE_URL = _get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
OLLAMA_MODEL = _get("OLLAMA_MODEL", "llama3.1:8b")
# Ollama needs no real key, but the OpenAI client requires a non-empty one.
OLLAMA_API_KEY = _get("OLLAMA_API_KEY", "ollama")

# --- Retrieval / answering ---
RETRIEVAL_MAX_DISTANCE = float(_get("RETRIEVAL_MAX_DISTANCE", "1.1"))

# --- App ---
PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(_get("DATA_DIR", "./data"))
CACHE_DIR = Path(_get("CACHE_DIR", "./cache"))
CHUNK_WORDS = int(_get("CHUNK_WORDS", "220"))
CHUNK_OVERLAP_WORDS = int(_get("CHUNK_OVERLAP_WORDS", "40"))
LLM_TOP_K = int(_get("LLM_TOP_K", "5"))
LLM_TEMPERATURE = float(_get("LLM_TEMPERATURE", "0.2"))

# Ensure directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)


@cache
def get_embedding_model():
    """Lazy singleton for the local sentence-transformers model."""
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(EMBEDDING_MODEL)


@cache
def get_chroma():
    """Lazy singleton for the ChromaDB persistent client."""
    import chromadb

    return chromadb.PersistentClient(path=str(CACHE_DIR / "chroma"))


@cache
def get_collection():
    """Lazy singleton for the vector collection (auto-created, cosine space)."""
    return get_chroma().get_or_create_collection(
        name=CHROMA_COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )


@cache
def get_llm_client():
    """Lazy singleton for the OpenAI-compatible Ollama client."""
    from openai import OpenAI

    return OpenAI(base_url=OLLAMA_BASE_URL, api_key=OLLAMA_API_KEY)


# Convenience: module-level attribute access for smoke tests.
# `from config import collection` triggers lazy init.
def __getattr__(name: str):
    if name == "collection":
        return get_collection()
    if name == "embedding_model":
        return get_embedding_model()
    if name == "llm_client":
        return get_llm_client()
    raise AttributeError(f"module 'config' has no attribute {name!r}")
