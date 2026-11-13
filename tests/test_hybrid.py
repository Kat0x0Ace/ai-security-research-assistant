"""Tests for hybrid retrieval: tokenizer, RRF fusion, BM25 index lifecycle, wiring."""

from __future__ import annotations

import pytest

import retrieval
from retrieval import rrf_fuse, tokenize


class TestTokenize:
    def test_basic(self):
        assert tokenize("What is RAG poisoning?") == ["what", "is", "rag", "poisoning"]

    def test_hyphenated_and_numbers(self):
        assert tokenize("OWASP LLM-Top-10 has 10 risks") == [
            "owasp", "llm", "top", "10", "has", "10", "risks",
        ]


class TestRRF:
    def test_union_ranking(self):
        fused = rrf_fuse(["a", "b", "c"], ["b", "d"])
        # 'b' ranks 1st on one list, 2nd on the other → top overall.
        assert fused[0] == "b"
        assert set(fused) == {"a", "b", "c", "d"}

    def test_order_matters(self):
        assert rrf_fuse(["a", "b"])[0] == "a"
        assert rrf_fuse(["b", "a"])[0] == "b"

    def test_k_constant(self):
        # 1st place on one list only: 1/(60+1) ≈ 0.0164
        fused = rrf_fuse(["a", "b"], k=60)
        assert fused == ["a", "b"]

    def test_empty_lists(self):
        assert rrf_fuse([], []) == []


class FakeCollection:
    """Minimal stand-in for the Chroma collection (get/query/count)."""

    def __init__(self, docs):
        self.docs = docs  # id -> (document, metadata)

    def count(self):
        return len(self.docs)

    def get(self, ids=None, include=None):
        ids = ids or list(self.docs)
        return {
            "ids": ids,
            "documents": [self.docs[cid][0] for cid in ids],
            "metadatas": [self.docs[cid][1] for cid in ids],
            "embeddings": [[1.0, 0.0]] * len(ids),
        }

    def query(self, query_embeddings=None, n_results=5):
        ordered = list(self.docs)[:n_results]
        return {
            "ids": [ordered],
            "documents": [[self.docs[cid][0] for cid in ordered]],
            "metadatas": [[self.docs[cid][1] for cid in ordered]],
            "distances": [[0.1 * (i + 1) for i in range(len(ordered))]],
        }


class TestBM25Index:
    def test_build_and_invalidate(self, monkeypatch):
        # rank_bm25's idf needs N large enough that a term in 1-of-N docs is
        # informative (ln((N-n+0.5)/(n+0.5)) > eps); 2 docs zero it out.
        docs = {f"id{i}": (text, {"source": "s.md", "chunk_index": i}) for i, text in enumerate([
            "the quick brown fox jumps",
            "the lazy dog sleeps all day",
            "owasp llm top 10 risks list",
            "prompt injection attacks on models",
            "jailbreak roleplay tricks escalate",
            "retrieval poisoning plants hidden instructions",
            "mitre atlas tracks adversarial ml threats",
            "guards defend against jailbreak attempts",
        ])}
        docs["id0"] = ("the quick brown fox jumps", {"source": "a.md", "chunk_index": 0})
        fake = FakeCollection(docs)
        monkeypatch.setattr(retrieval, "get_collection", lambda: fake)
        retrieval.invalidate_bm25()
        bm25, ids = retrieval.get_bm25()
        assert bm25 is not None and len(ids) == len(docs)
        # scores respond to a keyword query: 'fox' appears in exactly one chunk
        scores = bm25.get_scores(tokenize("fox jumps"))
        assert scores[0] == max(scores) and scores[0] > 0
        retrieval.invalidate_bm25()

    def test_empty_collection(self, monkeypatch):
        monkeypatch.setattr(retrieval, "get_collection", lambda: FakeCollection({}))
        retrieval.invalidate_bm25()
        assert retrieval.get_bm25() == (None, [])


class TestHybridEnabled:
    def test_default_on(self, monkeypatch):
        monkeypatch.delenv("HYBRID_SEARCH", raising=False)
        assert retrieval.hybrid_enabled() is True

    def test_off_via_env(self, monkeypatch):
        for val in ("0", "false", "no"):
            monkeypatch.setenv("HYBRID_SEARCH", val)
            assert retrieval.hybrid_enabled() is False


class TestRetrieveWiring:
    def test_rag_uses_hybrid_by_default(self, monkeypatch):
        """retrieve() routes through retrieve_hybrid when the flag is on."""
        import rag

        called = {}

        def fake_hybrid(query, top_k):
            called["query"] = query
            return [{"id": "x", "text": "t", "source": "s.md", "distance": 0.3}]

        monkeypatch.setattr(rag, "hybrid_enabled", lambda: True)
        monkeypatch.setattr(rag, "retrieve_hybrid", fake_hybrid)
        result = rag.retrieve("what is prompt injection?")
        assert called["query"] == "what is prompt injection?"
        assert result[0].source == "s.md" and result[0].distance == 0.3

    def test_rag_falls_back_to_vector(self, monkeypatch):
        import rag

        monkeypatch.setattr(rag, "hybrid_enabled", lambda: False)
        monkeypatch.setattr(
            rag, "retrieve_hybrid",
            lambda *a, **k: pytest.fail("hybrid path must not run when disabled"),
        )
        monkeypatch.setattr(rag, "get_collection", lambda: FakeCollection({}))
        assert rag.retrieve("anything") == []


class TestRetrieveHybridRealCollection:
    """End-to-end over a real (in-memory) ChromaDB collection — no fakes.

    Regression: when BM25 surfaced a chunk the vector search did not return,
    retrieve_hybrid crashed unpacking collection.get()'s result dict.
    """

    def test_bm25_only_chunk_is_returned_with_true_distance(self, monkeypatch):
        import uuid

        import chromadb
        import numpy as np

        import retrieval

        client = chromadb.EphemeralClient()
        col = client.get_or_create_collection(
            f"t-{uuid.uuid4().hex}", embedding_function=None, metadata={"hnsw:space": "cosine"}
        )
        query_vec = [1.0, 0.0, 0.0]
        # 7 fillers point near the query, so they fill the vector side's 6 slots...
        ids = [f"f{i}" for i in range(7)]
        docs = [f"generic filler text number {i}" for i in range(7)]
        embs = [[1.0, 0.05 * (i + 1), 0.0] for i in range(7)]
        # ...and one keyword-only chunk points away from it (vector search misses it).
        ids.append("kw")
        docs.append("the zebracorn keyword lives only here")
        embs.append([0.0, 0.0, 1.0])
        col.add(ids=ids, documents=docs, embeddings=embs,
                metadatas=[{"source": f"{cid}.md"} for cid in ids])

        monkeypatch.setattr(retrieval, "get_collection", lambda: col)
        monkeypatch.setattr(retrieval, "embed_query", lambda q: query_vec)
        retrieval.invalidate_bm25()
        try:
            hits = retrieval.retrieve_hybrid("zebracorn", top_k=3)
        finally:
            retrieval.invalidate_bm25()

        by_id = {h["id"]: h for h in hits}
        assert "kw" in by_id, "BM25-only chunk should be fused into the results"
        kw = by_id["kw"]
        assert kw["text"] == "the zebracorn keyword lives only here"
        assert kw["source"] == "kw.md"
        # true cosine distance between [1,0,0] and [0,0,1] is 1.0
        assert np.isclose(kw["distance"], 1.0)
