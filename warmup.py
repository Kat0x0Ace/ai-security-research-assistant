"""Load slow resources in the background when the app starts.

Measured: the first question after launch spent ~14s loading the embedding
model, and Ollama takes ~12s to load the LLM if it was unloaded. Doing both on
a background thread at startup means the user's first question doesn't pay for it.
Failures are logged and ignored — the normal request path still loads lazily.
"""

from __future__ import annotations

import json
import logging
import threading
import urllib.request

from config import OLLAMA_BASE_URL, OLLAMA_MODEL, get_embedding_model

log = logging.getLogger(__name__)

_started = False
_start_lock = threading.Lock()


def start_warmup() -> None:
    """Start the warm-up thread once per process (safe to call on every Streamlit rerun)."""
    global _started
    with _start_lock:
        if _started:
            return
        _started = True
    threading.Thread(target=_warm, name="warmup", daemon=True).start()


def _warm() -> None:
    try:
        get_embedding_model().encode("warm up")
    except Exception:
        log.exception("Embedding model warm-up failed")
    try:
        _load_ollama_model()
    except Exception:
        log.warning("Ollama warm-up failed (is Ollama running?)", exc_info=True)


def _load_ollama_model() -> None:
    """A generate call with no prompt makes Ollama load the model into memory."""
    base = OLLAMA_BASE_URL.removesuffix("/").removesuffix("/v1")
    body = json.dumps({"model": OLLAMA_MODEL}).encode()
    request = urllib.request.Request(f"{base}/api/generate", body, {"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=120) as response:
        response.read()
