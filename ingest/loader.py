"""Load documents from the data directory into (source, text) pairs.

Supported formats (v2):
  - .txt / .md  : read as UTF-8 text
  - .pdf        : extracted per-page via pypdf

Anything else is skipped with a notice — multimodal ingestion is parked.
"""

from __future__ import annotations

from pathlib import Path

TEXT_SUFFIXES = {".txt", ".md"}


def load_document(path: Path) -> list[tuple[str, str]]:
    """Return [(part_name, text), ...] for one file. Empty list = unsupported/empty."""
    suffix = path.suffix.lower()
    if suffix in TEXT_SUFFIXES:
        text = path.read_text(encoding="utf-8", errors="replace").strip()
        return [(path.name, text)] if text else []

    if suffix == ".pdf":
        return _load_pdf(path)

    print(f"[loader] skipping unsupported file: {path.name}")
    return []


def _load_pdf(path: Path) -> list[tuple[str, str]]:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            pages.append((f"{path.name}#page{i}", text))
    return pages


def load_data_dir(data_dir: Path) -> list[tuple[str, str]]:
    """Load every supported document in data_dir (recursive).

    Returns [(part_name, text), ...] where part_name identifies the exact
    source (file, or file#pageN for PDFs) for citation display.
    """
    pairs: list[tuple[str, str]] = []
    for path in sorted(data_dir.rglob("*")):
        if path.is_file() and not path.name.startswith("."):
            pairs.extend(load_document(path))
    return pairs
