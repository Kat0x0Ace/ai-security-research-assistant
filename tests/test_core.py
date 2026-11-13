"""Unit tests for chunker, loader, cache, and refusal logic (no LLM needed)."""

from __future__ import annotations

import pytest

from ingest.chunker import chunk_text


class TestChunker:
    def test_basic_overlap(self):
        words = [f"w{i}" for i in range(1000)]
        text = " ".join(words)
        chunks = chunk_text(text, chunk_words=220, overlap_words=40)
        assert len(chunks) > 1
        # consecutive chunks must share the overlap region
        first_end = chunks[0].split()[-40:]
        second_start = chunks[1].split()[:40]
        assert first_end == second_start

    def test_short_text_single_chunk(self):
        assert chunk_text("hello world") == ["hello world"]

    def test_empty_text(self):
        assert chunk_text("") == []
        assert chunk_text("   \n  ") == []

    def test_invalid_params(self):
        with pytest.raises(ValueError):
            chunk_text("text", chunk_words=10, overlap_words=10)

    def test_no_word_loss(self):
        words = [f"w{i}" for i in range(500)]
        text = " ".join(words)
        chunks = chunk_text(text, chunk_words=220, overlap_words=40)
        assert chunks[0].split()[0] == "w0"
        assert chunks[-1].split()[-1] == "w499"


class TestLoader:
    def test_txt_and_md(self, tmp_path):
        from ingest.loader import load_data_dir

        (tmp_path / "a.txt").write_text("alpha content")
        (tmp_path / "b.md").write_text("beta content")
        (tmp_path / "c.bin").write_bytes(b"\x00\x01")
        pairs = load_data_dir(tmp_path)
        names = [p[0] for p in pairs]
        assert names == ["a.txt", "b.md"]
        assert pairs[0][1] == "alpha content"

    def test_empty_file_skipped(self, tmp_path):
        from ingest.loader import load_data_dir

        (tmp_path / "empty.txt").write_text("")
        assert load_data_dir(tmp_path) == []


class TestCache:
    def test_roundtrip(self, tmp_path, monkeypatch):
        # point the cache at a temp dir, then reload the module
        import importlib

        import config

        monkeypatch.setattr(config, "CACHE_DIR", tmp_path)
        import ingest.cache as cache_mod

        importlib.reload(cache_mod)
        cache_mod.put(b"some content", "document", [0.1, 0.2, 0.3])
        assert cache_mod.get(b"some content", "document") == [0.1, 0.2, 0.3]
        assert cache_mod.get(b"other content", "document") is None

    def test_key_varies_by_task_type(self, tmp_path, monkeypatch):
        import importlib

        import config

        monkeypatch.setattr(config, "CACHE_DIR", tmp_path)
        import ingest.cache as cache_mod

        importlib.reload(cache_mod)
        cache_mod.put(b"content", "document", [1.0])
        assert cache_mod.get(b"content", "query") is None


class TestRefusal:
    def test_refusal_on_distant_hit(self, monkeypatch):
        import rag
        from rag import RetrievedChunk

        # top hit far beyond threshold -> must refuse without calling the LLM
        monkeypatch.setattr(
            rag,
            "retrieve",
            lambda q, top_k=5: [RetrievedChunk(text="x", source="s", distance=1.9)],
        )
        called = {"llm": False}
        monkeypatch.setattr(rag, "get_llm_client", lambda: (_ for _ in ()).throw(AssertionError("LLM should not be called on refusal")))
        result = rag.answer("anything")
        assert result.refused is True
        assert result.answer == rag.REFUSAL_TEXT
        assert not called["llm"]

    def test_refusal_on_empty_index(self, monkeypatch):
        import rag

        monkeypatch.setattr(rag, "retrieve", lambda q, top_k=5: [])
        result = rag.answer("anything")
        assert result.refused is True

    def test_system_prompt_wraps_untrusted(self):
        import rag

        assert "<untrusted" in rag._SYSTEM_PROMPT
        assert "never follow" in rag._SYSTEM_PROMPT


class TestRefusalGateUsesClosestPassage:
    """With hybrid retrieval the top fused hit isn't always the closest one."""

    def _hits(self, *distances):
        from rag import RetrievedChunk

        return [RetrievedChunk(text=f"t{i}", source=f"s{i}", distance=d) for i, d in enumerate(distances)]

    def test_close_passage_below_top_hit_is_not_refused(self, monkeypatch):
        import rag

        monkeypatch.setattr(rag, "retrieve", lambda q, top_k=5: self._hits(0.90, 0.30))
        early, hits = rag._prepare("a real question", top_k=2)
        assert early is None and len(hits) == 2

    def test_all_passages_far_is_refused(self, monkeypatch):
        import rag

        monkeypatch.setattr(rag, "retrieve", lambda q, top_k=5: self._hits(0.90, 0.85))
        early, _ = rag._prepare("off topic", top_k=2)
        assert early is not None and early.refused
