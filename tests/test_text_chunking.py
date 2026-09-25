from __future__ import annotations

import pytest

from jobpilot.utils.text import chunk_text, clean_posting_text, strip_html


def test_strip_html_removes_tags():
    assert strip_html("<p>Hello <b>world</b></p>") == "Hello world"


def test_clean_posting_text_normalizes_bullets_and_whitespace():
    raw = "<p>Responsibilities:</p>\n• Do thing one\n* Do thing two\n\n\n\nEnd."
    cleaned = clean_posting_text(raw)
    assert "- Do thing one" in cleaned
    assert "- Do thing two" in cleaned
    assert "\n\n\n" not in cleaned


def test_chunk_text_returns_whole_text_if_short():
    text = "short paragraph"
    assert chunk_text(text, max_chars=2000) == [text]


def test_chunk_text_splits_long_text_on_paragraphs():
    paragraphs = [f"Paragraph {i} " + ("word " * 30) for i in range(10)]
    text = "\n\n".join(paragraphs)
    chunks = chunk_text(text, max_chars=200, overlap_chars=20)
    assert len(chunks) > 1
    assert all(len(c) <= 220 for c in chunks)  # allow small overlap slack


def test_chunk_text_hard_splits_a_single_giant_paragraph():
    text = "x" * 5000
    chunks = chunk_text(text, max_chars=1000, overlap_chars=100)
    assert len(chunks) >= 5
    for chunk in chunks:
        assert len(chunk) <= 1000


def test_chunk_text_rejects_bad_overlap():
    with pytest.raises(ValueError):
        chunk_text("hello", max_chars=10, overlap_chars=10)


def test_chunk_text_empty_string_returns_empty_list():
    assert chunk_text("   ") == []
