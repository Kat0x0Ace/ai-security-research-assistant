"""Tests for conversation memory: follow-up detection, rewrite, fallback, wiring."""

from __future__ import annotations

import pytest

import rag
from rag import _looks_like_followup, rewrite_followup


class FakeCompletions:
    def __init__(self, reply: str):
        self._reply = reply
        self.last_messages = None

    def create(self, **kwargs):
        self.last_messages = kwargs.get("messages")
        obj = type("Resp", (), {})()
        obj.choices = [type("Choice", (), {})()]
        obj.choices[0].message = type("Msg", (), {})()
        obj.choices[0].message.content = self._reply
        return obj


class FakeClient:
    def __init__(self, reply: str = ""):
        self.chat = type("Chat", (), {})()
        self.chat.completions = FakeCompletions(reply)


class TestFollowupDetection:
    def test_pronoun_openers(self):
        assert _looks_like_followup("it also attacks PDFs?")
        assert _looks_like_followup("That's interesting")
        assert _looks_like_followup("tell me more")

    def test_standalone_questions(self):
        assert not _looks_like_followup("What is prompt injection?")
        assert not _looks_like_followup("How do multi-turn jailbreaks work?")
        assert not _looks_like_followup("Does citation enforcement help against indirect injection?")

    def test_word_boundary(self):
        # "theater" starts with "the" but must not match "this/that/these"
        assert not _looks_like_followup("theater of war in ancient rome?")


class TestRewrite:
    HISTORY = [("What is prompt injection?", "Prompt injection is an attack where...")]

    def test_no_history_passthrough(self):
        assert rewrite_followup("it also hits PDFs?", None) == "it also hits PDFs?"

    def test_standalone_skips_llm(self):
        # Standalone questions must not touch the LLM at all.
        client = FakeClient(reply="SHOULD NOT BE RETURNED")
        monkey = pytest.MonkeyPatch()
        monkey.setattr(rag, "get_llm_client", lambda: client)
        try:
            assert rewrite_followup("What is RAG poisoning?", self.HISTORY) == "What is RAG poisoning?"
        finally:
            monkey.undo()

    def test_followup_rewritten(self):
        import unittest.mock as mock

        client = FakeClient(reply="Does prompt injection also attack PDF ingestion?")
        with mock.patch.object(rag, "get_llm_client", lambda: client):
            result = rewrite_followup("does it also attack PDF ingestion?", self.HISTORY)
        assert result == "Does prompt injection also attack PDF ingestion?"

    def test_fallback_on_llm_failure(self):
        import unittest.mock as mock

        def broken():
            raise ConnectionError("ollama down")

        with mock.patch.object(rag, "get_llm_client", broken):
            result = rewrite_followup("tell me more", self.HISTORY)
        assert result == "tell me more (regarding: What is prompt injection?)"

    def test_empty_llm_reply_falls_back_to_query(self):
        import unittest.mock as mock

        with mock.patch.object(rag, "get_llm_client", lambda: FakeClient(reply="")):
            result = rewrite_followup("more?", self.HISTORY)
        assert result == "more?"


class TestHistoryExtraction:
    def _app_history(self):
        # import here so Streamlit import issues surface as a clear error
        from app import _recent_history
        return _recent_history

    def test_only_grounded_answers_count(self):
        messages = [
            {"role": "user", "content": "q1"},
            {"role": "assistant", "kind": "answer", "content": "a1", "sources": [1]},
            {"role": "user", "content": "q2"},
            {"role": "assistant", "kind": "refusal", "content": "I don't have...", "sources": []},
            {"role": "user", "content": "q3"},
            {"role": "assistant", "kind": "error", "content": "err", "sources": []},
            {"role": "user", "content": "q4"},
            {"role": "assistant", "kind": "answer", "content": "a4", "sources": [2]},
        ]
        pairs = self._app_history()(messages)
        assert pairs == [("q1", "a1"), ("q4", "a4")]

    def test_max_turns(self):
        messages = []
        for i in range(10):
            messages.append({"role": "user", "content": f"q{i}"})
            messages.append({"role": "assistant", "kind": "answer", "content": f"a{i}", "sources": []})
        pairs = self._app_history()(messages, max_turns=3)
        assert [q for q, _ in pairs] == ["q7", "q8", "q9"]

    def test_empty(self):
        assert self._app_history()([]) == []
