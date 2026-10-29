"""Chunk text into overlapping word windows.

Word-based (not tokenizer-based) so there is no extra model dependency at
chunk time; the sizes are calibrated so chunks fit well inside the local
LLM's context window after top-k assembly.
"""

from __future__ import annotations

from config import CHUNK_OVERLAP_WORDS, CHUNK_WORDS


def chunk_text(
    text: str,
    chunk_words: int = CHUNK_WORDS,
    overlap_words: int = CHUNK_OVERLAP_WORDS,
) -> list[str]:
    """Split text into overlapping chunks on word boundaries.

    Keeps whitespace normalized: paragraphs are preserved as double newlines.
    """
    if chunk_words <= overlap_words:
        raise ValueError("chunk_words must be greater than overlap_words")

    words = text.split()
    if not words:
        return []

    chunks: list[str] = []
    step = chunk_words - overlap_words
    for start in range(0, len(words), step):
        window = words[start : start + chunk_words]
        chunk = " ".join(window).strip()
        if chunk:
            chunks.append(chunk)
        if start + chunk_words >= len(words):
            break
    return chunks
