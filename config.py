"""Single source of truth for env vars and client singletons.

Importing this module:
  - Loads .env
  - Validates required keys
  - Returns lazy-initialized clients via get_* functions
"""

from __future__ import annotations

import os
from functools import cache
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value or value.startswith("your_"):
        raise RuntimeError(
            f"Missing env var {name}. Set it in .env "
            f"(see .env.example for the placeholder format)."
        )
    return value


def _get(name: str, default: str) -> str:
    return os.environ.get(name, default).strip() or default


# --- Pinecone ---
PINECONE_INDEX_NAME = _get("PINECONE_INDEX_NAME", "multimodal-rag")
PINECONE_CLOUD = _get("PINECONE_CLOUD", "aws")
PINECONE_REGION = _get("PINECONE_REGION", "us-east-1")

# --- Gemini ---
EMBEDDING_MODEL = _get("EMBEDDING_MODEL", "gemini-embedding-2")
EMBEDDING_DIM = int(_get("EMBEDDING_DIM", "1536"))

# --- OpenRouter ---
OPENROUTER_MODEL = _get("OPENROUTER_MODEL", "anthropic/claude-sonnet-4.6")
OPENROUTER_BASE_URL = _get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

# --- App ---
PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(_get("DATA_DIR", "./data"))
CACHE_DIR = Path(_get("CACHE_DIR", "./cache"))
CHUNK_TEXT_TOKENS = int(_get("CHUNK_TEXT_TOKENS", "1000"))
CHUNK_TEXT_OVERLAP = int(_get("CHUNK_TEXT_OVERLAP", "200"))
VIDEO_CLIP_SECONDS = int(_get("VIDEO_CLIP_SECONDS", "110"))
LLM_TOP_K = int(_get("LLM_TOP_K", "5"))
LLM_TEMPERATURE = float(_get("LLM_TEMPERATURE", "0.2"))

# Ensure directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)


@cache
def get_gemini_client():
    """Lazy singleton for the Gemini SDK client."""
    from google import genai

    return genai.Client(api_key=_require("GEMINI_API_KEY"))


@cache
def get_pinecone():
    """Lazy singleton for the Pinecone control-plane client."""
    from pinecone import Pinecone

    return Pinecone(api_key=_require("PINECONE_API_KEY"))


@cache
def get_pinecone_index():
    """Lazy singleton for the Pinecone index handle.

    Auto-creates the index on first call if it does not exist.
    """
    from pinecone import ServerlessSpec

    pc = get_pinecone()
    existing = {idx["name"] for idx in pc.list_indexes()}

    if PINECONE_INDEX_NAME not in existing:
        print(
            f"[config] Creating Pinecone index '{PINECONE_INDEX_NAME}' "
            f"(dim={EMBEDDING_DIM}, metric=cosine, "
            f"serverless={PINECONE_CLOUD}/{PINECONE_REGION})..."
        )
        pc.create_index(
            name=PINECONE_INDEX_NAME,
            dimension=EMBEDDING_DIM,
            metric="cosine",
            spec=ServerlessSpec(cloud=PINECONE_CLOUD, region=PINECONE_REGION),
        )

    return pc.Index(PINECONE_INDEX_NAME)


@cache
def get_openrouter_client():
    """Lazy singleton for the OpenAI-compatible OpenRouter client."""
    from openai import OpenAI

    return OpenAI(
        api_key=_require("OPENROUTER_API_KEY"),
        base_url=OPENROUTER_BASE_URL,
    )


# Convenience: module-level attribute access for the DoD smoke test.
# `from config import pinecone_index` triggers lazy init.
def __getattr__(name: str):
    if name == "pinecone_index":
        return get_pinecone_index()
    if name == "gemini_client":
        return get_gemini_client()
    if name == "openrouter_client":
        return get_openrouter_client()
    raise AttributeError(f"module 'config' has no attribute {name!r}")
