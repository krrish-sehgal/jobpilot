from __future__ import annotations

import io
import zipfile

import pytest

from jobpilot.errors import FileTooLargeError, ResumeParseError, UnsupportedFileTypeError
from jobpilot.integrations.llm import FakeLLMClient
from jobpilot.resume.extract import FileKind, StubTextExtractor, detect_file_kind, validate_upload
from jobpilot.resume.parser import assign_ids, parse_resume
from tests.resume_fixtures import make_docx, make_pdf, sample_resume_json, sample_sections


def test_pdf_and_docx_are_detected_by_content():
    assert detect_file_kind(make_pdf()) is FileKind.PDF
    assert detect_file_kind(make_docx()) is FileKind.DOCX


@pytest.mark.parametrize(
    "data",
    [b"", b"MZ\x90\x00 an executable", b"plain text resume", b"PK\x03\x04 not really a zip"],
)
def test_other_content_is_rejected(data):
    with pytest.raises(UnsupportedFileTypeError):
        validate_upload(data)


def test_a_zip_without_word_document_is_not_a_docx():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("notes.txt", "hello")
    with pytest.raises(UnsupportedFileTypeError):
        validate_upload(buffer.getvalue())


def test_oversized_file_is_rejected_before_type_check():
    with pytest.raises(FileTooLargeError):
        validate_upload(b"%PDF-" + b"x" * 100, max_bytes=50)


def test_stub_extractor_reads_both_formats():
    extractor = StubTextExtractor()
    assert "Priya Nair" in extractor.extract(make_pdf(), FileKind.PDF)
    docx_text = extractor.extract(make_docx(["Line one", "Line two"]), FileKind.DOCX)
    assert docx_text.splitlines() == ["Line one", "Line two"]


def test_stub_extractor_rejects_an_empty_document():
    with pytest.raises(ResumeParseError):
        StubTextExtractor().extract(b"%PDF-1.4\n   ", FileKind.PDF)


def _llm_returning(content: str | None) -> FakeLLMClient:
    return FakeLLMClient(
        responder=lambda s, m: {"content": content, "tool_calls": [], "finish_reason": "stop"}
    )


def test_parse_assigns_stable_unique_ids():
    first = parse_resume(_llm_returning(sample_resume_json()), "resume text")
    second = parse_resume(_llm_returning(sample_resume_json()), "resume text")
    ids = [b.id for e in first.experience for b in e.bullets] + [e.id for e in first.experience]
    assert all(ids) and len(ids) == len(set(ids))
    assert first == second  # same input, same ids


def test_parse_accepts_a_fenced_json_reply():
    sections = parse_resume(_llm_returning(f"```json\n{sample_resume_json()}\n```"), "x")
    assert sections.contact.name == "Priya Nair"


@pytest.mark.parametrize("reply", [None, "", "not json at all", "[1, 2]", '{"skills": "python"}'])
def test_parse_failures_raise_a_domain_error(reply):
    with pytest.raises(ResumeParseError):
        parse_resume(_llm_returning(reply), "resume text")


def test_assign_ids_does_not_mutate_its_input():
    sections = sample_sections().model_copy(deep=True)
    sections.experience[0].id = ""
    assign_ids(sections)
    assert sections.experience[0].id == ""
