"""Tests for observability: turn logging, stats rollup, and RAG instrumentation."""

from __future__ import annotations

import json

import pytest

import observability
from observability import stats, summarize_line


@pytest.fixture()
def log_file(tmp_path, monkeypatch):
    """Point the log at a temp file and clear module-level path references."""
    path = tmp_path / "query_log.jsonl"
    monkeypatch.setattr(observability, "LOG_PATH", path)
    return path


class TestLogTurn:
    def test_writes_one_jsonl_line(self, log_file):
        observability.log_turn(
            "What is prompt injection?",
            sources=[("a.md", 0.23456), ("b.md", 0.56789)],
            refused=False,
            small_talk=False,
            retrieval_ms=12.34,
            total_ms=1050.0,
        )
        records = [json.loads(line) for line in log_file.read_text().splitlines()]
        assert len(records) == 1
        rec = records[0]
        assert rec["query"] == "What is prompt injection?"
        assert rec["best_distance"] == 0.2346
        assert rec["refused"] is False
        assert rec["retrieval_ms"] == 12.3
        assert rec["total_ms"] == 1050.0

    def test_never_raises_on_bad_path(self, tmp_path, monkeypatch):
        # Point the log somewhere unwritable (a file where the dir should be)
        blocker = tmp_path / "blocker"
        blocker.write_text("not a dir")
        monkeypatch.setattr(observability, "LOG_PATH", blocker / "nested" / "log.jsonl")
        observability.log_turn("q", sources=[], refused=False, small_talk=False, retrieval_ms=1.0)

    def test_appends_not_overwrites(self, log_file):
        for i in range(3):
            observability.log_turn(f"q{i}", sources=[], refused=False, small_talk=False, retrieval_ms=1.0)
        assert len(log_file.read_text().splitlines()) == 3


class TestStats:
    def test_missing_log_gives_zeros(self, tmp_path):
        s = stats(tmp_path / "nope.jsonl")
        assert s["total_turns"] == 0
        assert s["refusal_rate"] is None
        assert s["turns_by_source"] == {}

    def test_rolls_up_correctly(self, log_file):
        rows = [
            {"query": "a", "sources": [{"source": "x.md", "distance": 0.2}], "refused": False, "small_talk": False, "retrieval_ms": 10},
            {"query": "b", "sources": [{"source": "x.md", "distance": 0.3}], "refused": True, "small_talk": False, "retrieval_ms": 30},
            {"query": "c", "sources": [{"source": "y.md", "distance": 0.4}], "refused": False, "small_talk": False, "retrieval_ms": 20},
            {"query": "thanks", "sources": [], "refused": False, "small_talk": True, "retrieval_ms": 0.1},
        ]
        with log_file.open("w") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")
        s = stats(log_file)
        assert s["total_turns"] == 4
        assert s["real_turns"] == 3
        assert s["small_talk_turns"] == 1
        assert s["refusals"] == 1
        assert s["refusal_rate"] == round(1 / 3, 3)
        assert s["retrieval_ms_median"] == 20.0
        assert s["turns_by_source"] == {"x.md": 2, "y.md": 1}

    def test_corrupt_lines_skipped(self, log_file):
        log_file.write_text('{"query": "ok", "sources": [], "refused": false, "small_talk": false, "retrieval_ms": 5}\nGARBAGE\n')
        s = stats(log_file)
        assert s["total_turns"] == 1

    def test_summarize_line_with_data(self, log_file):
        observability.log_turn("q", sources=[("a.md", 0.3)], refused=False, small_talk=False, retrieval_ms=42.0, total_ms=900.0)
        line = summarize_line()
        assert "1 turns" in line and "42.0ms" in line

    def test_summarize_line_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr(observability, "LOG_PATH", tmp_path / "none.jsonl")
        assert summarize_line() == "no logged turns yet"


class TestRagInstrumentation:
    def test_answer_small_talk_is_logged(self, log_file, monkeypatch):
        # answer() should log even the turns that never reach retrieval or the LLM.
        from rag import answer

        monkeypatch.setattr("rag.get_llm_client", lambda: pytest.fail("LLM must not be called for small talk"))
        result = answer("thanks")
        assert result.small_talk
        rec = json.loads(log_file.read_text().splitlines()[-1])
        assert rec["small_talk"] is True and rec["query"] == "thanks"
