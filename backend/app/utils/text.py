"""PDF text extraction, cleaning, and chunking."""

from __future__ import annotations

import io
import re

from pypdf import PdfReader
from pypdf.errors import PdfReadError


class DocumentParseError(ValueError):
    """Raised when an uploaded file cannot be read as text."""


def extract_pdf_pages(data: bytes) -> list[str]:
    """Return the cleaned text of each page of a PDF."""
    try:
        reader = PdfReader(io.BytesIO(data))
    except (PdfReadError, OSError, ValueError) as exc:
        raise DocumentParseError(f"Could not read the PDF: {exc}") from exc

    if reader.is_encrypted:
        # An empty user password is common for "protected" but readable PDFs.
        try:
            reader.decrypt("")
        except Exception as exc:  # pypdf raises several types here
            raise DocumentParseError("The PDF is password protected") from exc

    pages: list[str] = []
    for page in reader.pages:
        try:
            pages.append(clean_text(page.extract_text() or ""))
        except Exception:  # a single malformed page should not fail the upload
            pages.append("")
    return pages


def clean_text(text: str) -> str:
    """Normalise whitespace and strip artefacts common in extracted PDF text."""
    # Re-join words hyphenated across a line break.
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    text = text.replace(" ", " ").replace("﻿", "")
    # Collapse runs of spaces/tabs but keep line structure, which carries the
    # section headings the offline resume parser relies on.
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(lines).strip()


def chunk_text(
    text: str, chunk_size: int, overlap: int
) -> list[str]:
    """Split text into overlapping chunks, preferring paragraph boundaries.

    Overlap keeps a requirement that straddles a boundary retrievable from either
    side of it.
    """
    text = text.strip()
    if not text:
        return []
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")
    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        if end < len(text):
            # Prefer to break on a paragraph, then a sentence, then a space.
            window = text[start:end]
            for separator in ("\n\n", "\n", ". ", " "):
                index = window.rfind(separator)
                # Only accept a break point in the last third of the window, so
                # chunks stay reasonably sized.
                if index > chunk_size * 0.6:
                    end = start + index + len(separator)
                    break
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(start + 1, end - overlap)
    return chunks


def page_for_offset(page_lengths: list[int], offset: int) -> int:
    """Map a character offset in the joined document back to a 1-indexed page."""
    running = 0
    for index, length in enumerate(page_lengths):
        running += length
        if offset < running:
            return index + 1
    return len(page_lengths) or 1
