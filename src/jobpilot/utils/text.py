"""Text cleaning and chunking utilities.

Used before embedding (chunk large descriptions to stay under a model's
context window) and before display (strip boilerplate HTML/markup that
scrapers occasionally pick up from a listing page).
"""

from __future__ import annotations

import re

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_MULTI_NEWLINE_RE = re.compile(r"\n{3,}")
_MULTI_SPACE_RE = re.compile(r"[ \t]{2,}")
_BULLET_PREFIX_RE = re.compile(r"^[•●\-\*]\s*", re.MULTILINE)


def strip_html(text: str) -> str:
    """Remove HTML tags, leaving their text content intact."""

    return _HTML_TAG_RE.sub("", text)


def clean_posting_text(text: str) -> str:
    """Normalize raw posting text for storage and display.

    Strips HTML, normalizes bullet characters to a plain hyphen,
    collapses runs of blank lines and repeated spaces, and trims each
    line.
    """

    without_html = strip_html(text)
    normalized_bullets = _BULLET_PREFIX_RE.sub("- ", without_html)
    lines = [line.rstrip() for line in normalized_bullets.splitlines()]
    joined = "\n".join(lines)
    joined = _MULTI_SPACE_RE.sub(" ", joined)
    joined = _MULTI_NEWLINE_RE.sub("\n\n", joined)
    return joined.strip()


def chunk_text(text: str, *, max_chars: int = 2000, overlap_chars: int = 200) -> list[str]:
    """Split `text` into overlapping chunks of at most `max_chars`.

    Splits on paragraph boundaries where possible so chunks don't cut
    a sentence in half; falls back to a hard character split for a
    single paragraph longer than `max_chars`. `overlap_chars` of
    trailing context is carried into the next chunk so a concept that
    spans a boundary isn't lost to either chunk alone.
    """

    if max_chars <= 0:
        raise ValueError("max_chars must be > 0")
    if overlap_chars < 0 or overlap_chars >= max_chars:
        raise ValueError("overlap_chars must be >= 0 and < max_chars")

    text = text.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    paragraphs = [p for p in re.split(r"\n{2,}", text) if p.strip()]
    if not paragraphs:
        paragraphs = [text]

    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}" if current else paragraph
        if len(candidate) <= max_chars:
            current = candidate
            continue

        if current:
            chunks.append(current)
            tail = current[-overlap_chars:] if overlap_chars else ""
            current = f"{tail}\n\n{paragraph}" if tail else paragraph
        else:
            current = paragraph

        # A single paragraph longer than max_chars: hard-split it.
        while len(current) > max_chars:
            chunks.append(current[:max_chars])
            current = current[max_chars - overlap_chars :]

    if current:
        chunks.append(current)

    return chunks
