"""SSE frame formatting and token chunking."""

from __future__ import annotations

import json

import pytest

from jobpilot.web.streaming import chunk_text, format_sse
from tests.web_fixtures import parse_sse


def test_frame_has_event_line_json_data_line_and_blank_terminator():
    frame = format_sse("tool_call", {"call_id": "c1", "name": "search_jobs", "label": "Searching"})
    lines = frame.split("\n")
    assert lines[0] == "event: tool_call"
    assert lines[1].startswith("data: ")
    assert json.loads(lines[1][6:]) == {
        "call_id": "c1",
        "name": "search_jobs",
        "label": "Searching",
    }
    assert frame.endswith("\n\n") and len(lines) == 4


def test_newlines_and_unicode_in_data_stay_on_one_line():
    frame = format_sse("token", {"text": "line one\nline two — café"})
    assert frame.count("\n") == 3  # event, data, terminator: no raw newline inside the data
    assert parse_sse(frame) == [("token", {"text": "line one\nline two — café"})]


def test_parse_ignores_keepalive_comments():
    body = ": keep-alive\n\n" + format_sse("done", {"message_id": "m"})
    assert parse_sse(body) == [("done", {"message_id": "m"})]


@pytest.mark.parametrize(
    "text",
    [
        "",
        "short",
        "A reply that is long enough to be split into several token chunks for the browser.",
        "line one\n\nline two with   odd   spacing\t and tabs",
        "x" * 200,
        "  leading and trailing  ",
    ],
)
def test_chunks_reassemble_exactly(text):
    assert "".join(chunk_text(text)) == text


def test_chunks_are_small_and_split_on_words():
    text = "word " * 40
    chunks = chunk_text(text, size=24)
    assert len(chunks) > 1
    assert all(len(c) <= 24 for c in chunks)
    assert all(c.endswith(" ") for c in chunks)  # whitespace stays with the word before it


def test_an_enormous_word_is_still_split():
    chunks = chunk_text("y" * 500, size=24)
    assert all(len(c) <= 48 for c in chunks)
    assert "".join(chunks) == "y" * 500
