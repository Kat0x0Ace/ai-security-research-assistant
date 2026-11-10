"""Lightweight observability: every RAG turn appends one JSONL record.

Portfolio rationale (the "observe" part of build+observe): you can't claim a
system works without numbers. This module records, per turn:

- the query text (kept local — the log file is gitignored, nothing uploads)
- retrieval outcome: sources returned, best cosine distance, refusal flag
- latency, split into retrieval vs. total where measurable
- small-talk short-circuit (turns that never touched retrieval or the LLM)

`stats()` rolls the log into the three numbers interviewers ask for:
refusal rate, median retrieval latency, and hit distribution by source.

The log lives under CACHE_DIR (default `cache/query_log.jsonl`) and is
append-only; a corrupt line is skipped, never fatal.
"""

from __future__ import annotations

import json
import os
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

from config import CACHE_DIR

LOG_PATH = CACHE_DIR / "query_log.jsonl"


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def log_turn(
    query: str,
    *,
    sources: list[tuple[str, float]],
    refused: bool,
    small_talk: bool,
    retrieval_ms: float,
    total_ms: float | None = None,
    streamed: bool = False,
) -> None:
    """Append one turn record. Never raises: logging must not break chat."""
    try:
        record = {
            "ts": _ts(),
            "query": query,
            "query_chars": len(query),
            "sources": [{"source": s, "distance": round(d, 4)} for s, d in sources],
            "best_distance": round(min((d for _, d in sources), default=float("inf")), 4) if sources else None,
            "refused": refused,
            "small_talk": small_talk,
            "retrieval_ms": round(retrieval_ms, 1),
            "total_ms": round(total_ms, 1) if total_ms is not None else None,
            "streamed": streamed,
        }
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:  # disk full, permissions — chat continues regardless
        pass


class Timer:
    """Small monotonic timer: `with Timer() as t:` → t.ms."""

    def __enter__(self) -> "Timer":
        self._start = time.perf_counter()
        self.ms = 0.0
        return self

    def __exit__(self, *exc) -> None:
        self.ms = (time.perf_counter() - self._start) * 1000


def stats(path: Path | None = None) -> dict:
    """Roll the query log into summary numbers. Missing/empty log → zeros."""
    path = path or LOG_PATH
    turns: list[dict] = []
    if path.exists():
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    turns.append(json.loads(line))
                except json.JSONDecodeError:
                    continue  # skip corrupt lines
    real = [t for t in turns if not t.get("small_talk")]
    retrieval_ms = [t["retrieval_ms"] for t in real if t.get("retrieval_ms") is not None]
    total_ms = [t["total_ms"] for t in real if t.get("total_ms") is not None]
    refused = sum(1 for t in real if t.get("refused"))
    by_source: dict[str, int] = {}
    for t in real:
        for s in t.get("sources", []):
            by_source[s["source"]] = by_source.get(s["source"], 0) + 1
    return {
        "total_turns": len(turns),
        "real_turns": len(real),
        "small_talk_turns": len(turns) - len(real),
        "refusals": refused,
        "refusal_rate": round(refused / len(real), 3) if real else None,
        "retrieval_ms_median": round(statistics.median(retrieval_ms), 1) if retrieval_ms else None,
        "total_ms_median": round(statistics.median(total_ms), 1) if total_ms else None,
        "turns_by_source": dict(sorted(by_source.items(), key=lambda kv: -kv[1])),
    }


def summarize_line() -> str:
    """One-line human summary for the README badge / terminal."""
    s = stats()
    if not s["real_turns"]:
        return "no logged turns yet"
    parts = [
        f"{s['real_turns']} turns",
        f"refusal rate {s['refusal_rate']:.0%}",
    ]
    if s["retrieval_ms_median"] is not None:
        parts.append(f"retrieval median {s['retrieval_ms_median']}ms")
    if s["total_ms_median"] is not None:
        parts.append(f"total median {s['total_ms_median']}ms")
    return " · ".join(parts)
