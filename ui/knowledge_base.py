"""Human-readable titles for the documents in the data folder.

Used by the sidebar ("What I know") and to label citations, so the UI shows
"Prompt Injection Basics" instead of "prompt-injection-basics.md".
"""

from __future__ import annotations

from pathlib import Path

from ingest.loader import TEXT_SUFFIXES

SUPPORTED_SUFFIXES = TEXT_SUFFIXES | {".pdf"}


def document_titles(data_dir: Path) -> dict[str, str]:
    """Map each supported file name in data_dir (recursive) to a display title."""
    titles: dict[str, str] = {}
    for path in sorted(data_dir.rglob("*")):
        if path.is_file() and not path.name.startswith(".") and path.suffix.lower() in SUPPORTED_SUFFIXES:
            titles[path.name] = _title_for(path)
    return titles


def source_title(source: str, titles: dict[str, str]) -> str:
    """Display title for a citation source ("file.pdf#page3" -> "Title · p.3")."""
    name, _, page = source.partition("#page")
    title = titles.get(name) or _prettify(Path(name).stem)
    return f"{title} · p.{page}" if page else title


def _title_for(path: Path) -> str:
    """First markdown '# ' heading for .md files, otherwise a prettified file name."""
    if path.suffix.lower() == ".md":
        try:
            with path.open(encoding="utf-8", errors="replace") as f:
                for _ in range(20):  # only look near the top of the file
                    line = f.readline()
                    if not line:
                        break
                    if line.startswith("# "):
                        return line[2:].strip()
        except OSError:
            pass
    return _prettify(path.stem)


def _prettify(stem: str) -> str:
    return stem.replace("-", " ").replace("_", " ").strip().capitalize()
