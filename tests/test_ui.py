"""Tests for small-talk handling, safe HTML rendering, and document titles (no LLM needed)."""

from __future__ import annotations

import pytest

from ui.knowledge_base import document_titles, source_title
from ui.render import answer_html, match_strength, sources_html, user_bubble_html


class TestSmallTalk:
    @pytest.mark.parametrize("msg", ["thanks!", "Thank you so much", "ok cool", "hi", "Hello there", "ok thanks", "bye!", "great, thanks!"])
    def test_detected(self, msg):
        from rag import small_talk_reply

        assert small_talk_reply(msg) is not None

    @pytest.mark.parametrize("msg", [
        "What is prompt injection?",
        "thanks, and what is MITRE ATLAS?",
        "how do I say hi to a model safely",
        "ok so what is RAG poisoning",
        "",
    ])
    def test_real_questions_not_small_talk(self, msg):
        from rag import small_talk_reply

        assert small_talk_reply(msg) is None

    def test_thanks_gets_thanks_reply(self):
        from rag import small_talk_reply

        assert small_talk_reply("ok thanks!").startswith("You're welcome")

    def test_small_talk_skips_retrieval_and_llm(self, monkeypatch):
        import rag

        monkeypatch.setattr(rag, "retrieve", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no retrieval")))
        monkeypatch.setattr(rag, "get_llm_client", lambda: (_ for _ in ()).throw(AssertionError("no LLM")))
        result = rag.answer("thanks!")
        assert result.small_talk is True
        assert result.sources == []


class TestRefusalCleanup:
    def test_refuse_then_answer_is_cut(self, monkeypatch):
        """If the model refuses and then answers from memory anyway, only the refusal survives."""
        import rag
        from rag import RetrievedChunk

        monkeypatch.setattr(rag, "retrieve", lambda q, top_k=5: [RetrievedChunk(text="x", source="s", distance=0.3)])

        class FakeClient:
            class chat:
                class completions:
                    @staticmethod
                    def create(**_):
                        msg = type("M", (), {"content": rag.REFUSAL_TEXT + "\n\nHowever, from general knowledge..."})
                        return type("R", (), {"choices": [type("C", (), {"message": msg})]})

        monkeypatch.setattr(rag, "get_llm_client", lambda: FakeClient)
        result = rag.answer("anything")
        assert result.refused is True
        assert result.answer == rag.REFUSAL_TEXT


class TestStreaming:
    def _fake_stream(self, monkeypatch, pieces):
        import rag
        from rag import RetrievedChunk

        monkeypatch.setattr(rag, "retrieve", lambda q, top_k=5: [RetrievedChunk(text="x", source="s", distance=0.3)])

        def chunk(text):
            delta = type("D", (), {"content": text})
            return type("K", (), {"choices": [type("C", (), {"delta": delta})]})

        class FakeStream:
            closed = False
            def __iter__(self):
                return iter([chunk(p) for p in pieces])
            def close(self):
                FakeStream.closed = True

        class FakeClient:
            class chat:
                class completions:
                    @staticmethod
                    def create(**kwargs):
                        assert kwargs["stream"] is True
                        return FakeStream()

        monkeypatch.setattr(rag, "get_llm_client", lambda: FakeClient)
        return FakeStream

    def test_normal_answer_streams_in_full(self, monkeypatch):
        import rag

        stream_cls = self._fake_stream(monkeypatch, ["Indirect ", "injection is ", "bad [1]."])
        result, pieces = rag.stream_answer("q")
        assert "".join(pieces) == "Indirect injection is bad [1]."
        assert result.answer == "Indirect injection is bad [1]." and not result.refused
        assert stream_cls.closed

    def test_refuse_then_hallucinate_never_shown(self, monkeypatch):
        import rag

        text = rag.REFUSAL_TEXT + " However, from general knowledge Paris is..."
        self._fake_stream(monkeypatch, [text[i:i + 7] for i in range(0, len(text), 7)])
        result, pieces = rag.stream_answer("q")
        shown = "".join(pieces)
        assert "Paris" not in shown and shown == ""
        assert result.refused and result.answer == rag.REFUSAL_TEXT

    def test_answer_starting_with_I_is_released(self, monkeypatch):
        import rag

        self._fake_stream(monkeypatch, ["I", " think ", "the sources say X [1]."])
        result, pieces = rag.stream_answer("q")
        assert "".join(pieces) == "I think the sources say X [1]."
        assert not result.refused

    def test_small_talk_not_streamed(self):
        import rag

        result, pieces = rag.stream_answer("thanks!")
        assert pieces is None and result.small_talk


class TestSafeRendering:
    def test_script_in_answer_is_escaped(self):
        out = answer_html('Hi <script>alert(1)</script> <img src=x onerror=alert(1)> [1]')
        assert "<script>" not in out
        assert "<img" not in out
        assert "&lt;script&gt;" in out
        assert '<span class="cite">1</span>' in out

    def test_markdown_image_and_link_not_rendered(self):
        out = answer_html("![x](https://evil.example/?q=secret) [click](https://evil.example)")
        assert "<img" not in out and "<a " not in out

    def test_bold_cannot_smuggle_html(self):
        out = answer_html("**<b onclick=x>hi</b>**")
        assert "<b " not in out
        assert "<strong>&lt;b onclick=x&gt;hi&lt;/b&gt;</strong>" in out

    def test_grouped_citations_and_lists(self):
        out = answer_html("Intro [1, 2]\n\n- one [3]\n- two")
        assert out.count('class="cite"') == 3
        assert "<ul><li>one" in out

    def test_user_bubble_escaped(self):
        assert "<script>" not in user_bubble_html("<script>x</script>")

    def test_sources_escaped(self):
        out = sources_html([{"title": "<b>t</b>", "text": "<script>x</script>", "distance": 0.3}])
        assert "<script>" not in out and "<b>t</b>" not in out

    def test_excerpt_drops_leading_title(self):
        # Real chunks are single-line word windows (see ingest/chunker.py).
        text = "# Prompt Injection Basics Prompt injection is an attack. ## Defenses Use layers."
        out = sources_html([{"title": "Prompt Injection Basics", "text": text, "distance": 0.3}])
        assert "Prompt Injection Basics Prompt injection" not in out
        assert "Prompt injection is an attack. Defenses Use layers." in out

    def test_excerpt_kept_when_no_title_prefix(self):
        out = sources_html([{"title": "Prompt Injection Basics", "text": "a successful injection cannot do damage", "distance": 0.3}])
        assert "a successful injection cannot do damage" in out

    def test_match_strength(self):
        assert match_strength(0.29)[0] == "strong match"
        assert match_strength(0.5)[0] == "good match"
        assert match_strength(0.7)[0] == "partial match"
        assert 5 <= match_strength(1.9)[1] <= 100


class TestTitles:
    def test_md_heading_and_fallback(self, tmp_path):
        (tmp_path / "a-doc.md").write_text("# Real Title\nbody", encoding="utf-8")
        (tmp_path / "notes_file.txt").write_text("plain", encoding="utf-8")
        (tmp_path / "skip.png").write_bytes(b"x")
        titles = document_titles(tmp_path)
        assert titles == {"a-doc.md": "Real Title", "notes_file.txt": "Notes file"}

    def test_pdf_page_source(self):
        assert source_title("report.pdf#page3", {"report.pdf": "Report"}) == "Report · p.3"
        assert source_title("unknown-file.md", {}) == "Unknown file"
