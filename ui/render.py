"""Turn chat content into HTML for display.

SECURITY: model answers and document excerpts are UNTRUSTED. A poisoned document
can steer the model into emitting HTML, scripts or remote-image markdown (a data
exfiltration trick). So every piece of untrusted text is html-escaped FIRST, and
only then do we add our own fixed markup (citation badges, paragraphs, bold,
lists). Nothing here passes untrusted text through unescaped, and we never hand
it to st.markdown as markdown (which would render links and remote images).

These are pure functions (no Streamlit) so they can be unit-tested.
"""

from __future__ import annotations

import html
import re

_CITATION_RE = re.compile(r"\[(\d{1,2}(?:\s*,\s*\d{1,2})*)\]")
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_BULLET_RE = re.compile(r"^\s*[-*•]\s+(.*)$")
_NUMBERED_RE = re.compile(r"^\s*\d{1,2}[.)]\s+(.*)$")
_HEADING_RE = re.compile(r"^\s*#{1,6}\s+(.*)$")

EXCERPT_CHARS = 220


def answer_html(text: str) -> str:
    """Escaped answer with [n] citation badges and a small safe markdown subset."""
    blocks: list[str] = []
    paragraph: list[str] = []
    list_tag: str | None = None
    items: list[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            blocks.append("<p>" + "<br>".join(paragraph) + "</p>")
            paragraph.clear()

    def flush_list() -> None:
        nonlocal list_tag
        if list_tag:
            blocks.append(f"<{list_tag}>" + "".join(f"<li>{i}</li>" for i in items) + f"</{list_tag}>")
            items.clear()
            list_tag = None

    for raw_line in text.splitlines():
        if not raw_line.strip():
            flush_paragraph()
            flush_list()
            continue
        for tag, pattern in (("ul", _BULLET_RE), ("ol", _NUMBERED_RE)):
            match = pattern.match(raw_line)
            if match:
                flush_paragraph()
                if list_tag != tag:
                    flush_list()
                    list_tag = tag
                items.append(_inline(match.group(1)))
                break
        else:
            flush_list()
            heading = _HEADING_RE.match(raw_line)
            line = f"**{heading.group(1)}**" if heading else raw_line.strip()
            paragraph.append(_inline(line))

    flush_paragraph()
    flush_list()
    return '<div class="answer">' + "".join(blocks) + "</div>"


def _inline(line: str) -> str:
    """Escape one line, then add bold and citation badges."""
    escaped = html.escape(line)
    escaped = _BOLD_RE.sub(r"<strong>\1</strong>", escaped)
    return _CITATION_RE.sub(_badges, escaped)


def _badges(match: re.Match) -> str:
    numbers = [n.strip() for n in match.group(1).split(",")]
    return "".join(f'<span class="cite">{n}</span>' for n in numbers)


def user_bubble_html(text: str) -> str:
    body = "<br>".join(html.escape(line) for line in text.strip().splitlines())
    return f'<div class="user-row"><div class="user-bubble">{body}</div></div>'


def refusal_html() -> str:
    return (
        '<div class="refusal"><div class="tag">Outside the knowledge base</div>'
        "<p>I don't have material on that, so I won't guess. "
        "I can answer questions about the topics listed on the left.</p></div>"
    )


def thinking_html(source_count: int) -> str:
    """Shown while the model reads the sources, before its first words arrive."""
    noun = "source" if source_count == 1 else "sources"
    return f'<div class="thinking"><span></span><span></span><span></span>Reading {source_count} {noun}…</div>'


def error_html(message: str) -> str:
    return f'<div class="app-error"><div class="tag">Something went wrong</div><p>{html.escape(message)}</p></div>'


def verification_html(verification: dict | None) -> str:
    """One line under an answer with the citation-check outcome.

    `verification` is {"status", "checked", "flagged"} (see app.py). Flagged
    sentences are untrusted model output — escaped like everything else here.
    """
    if not verification:
        return ""
    status = verification.get("status")
    checked = verification.get("checked", 0)
    if status == "ok":
        noun = "claim" if checked == 1 else "claims"
        return f'<div class="verify ok">✓ {checked} cited {noun} checked against their sources</div>'
    if status == "flagged":
        items = "".join(f"<li>{html.escape(s)}</li>" for s in verification.get("flagged", []))
        return (
            '<div class="verify warn"><div class="tag">Not supported by the cited source</div>'
            f"<ul>{items}</ul>"
            "<p>The cited passage doesn't back these sentences up — treat them as unverified.</p></div>"
        )
    if status == "uncited":
        return (
            '<div class="verify warn"><div class="tag">No citations</div>'
            "<p>This answer cites no sources, so nothing in it could be checked — treat it with care.</p></div>"
        )
    return '<div class="verify dim">Citation check unavailable for this answer.</div>'


def match_strength(distance: float) -> tuple[str, int]:
    """Label + bar width (%) for a cosine distance (lower = closer)."""
    label = "strong match" if distance < 0.4 else "good match" if distance < 0.6 else "partial match"
    width = max(5, min(100, round((1 - distance) * 100)))
    return label, width


def _excerpt_text(text: str, title: str) -> str:
    """Passage text for display. Chunks are single-line word windows, so the first
    chunk of a file starts with "# <Title> ..."; drop the markdown markers and the
    leading title (it's already shown above the excerpt)."""
    excerpt = " ".join(text.replace("#", " ").split())
    if title and excerpt.lower().startswith(title.lower()):
        excerpt = excerpt[len(title):].lstrip()
    return excerpt


def sources_html(sources: list[dict]) -> str:
    """Numbered source rows. Each source: {"title", "text", "distance"}."""
    rows = []
    for i, src in enumerate(sources, start=1):
        label, width = match_strength(src["distance"])
        excerpt = _excerpt_text(src["text"], src["title"])
        if len(excerpt) > EXCERPT_CHARS:
            excerpt = excerpt[:EXCERPT_CHARS].rsplit(" ", 1)[0] + "…"
        rows.append(
            f'<div class="src"><div class="n">[{i}]</div>'
            f'<div><div class="t">{html.escape(src["title"])}</div><div class="x">{html.escape(excerpt)}</div></div>'
            f'<div class="match">{label}<div class="bar"><i style="width:{width}%"></i></div></div></div>'
        )
    return "".join(rows)
