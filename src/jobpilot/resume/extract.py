"""Uploaded file -> plain text.

Two separate jobs live here and are kept apart on purpose:

1. `validate_upload` decides whether a file is acceptable at all. It
   trusts neither the file name nor the client-supplied content type: a
   PDF must start with the `%PDF-` magic bytes, and a DOCX must be a
   zip archive that actually contains `word/document.xml`. A renamed
   executable or a random zip fails here with a domain error.
2. A `TextExtractor` turns validated bytes into text. That is the part
   that needs heavyweight parsers, so it sits behind a protocol.
"""

from __future__ import annotations

import io
import re
import zipfile
from enum import StrEnum
from typing import Protocol

from jobpilot.errors import FileTooLargeError, ResumeParseError, UnsupportedFileTypeError

#: Default upload limit; overridden by `Settings.resume_max_bytes`.
DEFAULT_MAX_BYTES = 5 * 1024 * 1024

_PDF_MAGIC = b"%PDF-"
_DOCX_REQUIRED_MEMBER = "word/document.xml"


class FileKind(StrEnum):
    PDF = "pdf"
    DOCX = "docx"


def detect_file_kind(data: bytes) -> FileKind | None:
    """Identify a file by its content, not its name. `None` if unsupported."""

    if data.startswith(_PDF_MAGIC):
        return FileKind.PDF
    if data.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                if _DOCX_REQUIRED_MEMBER in archive.namelist():
                    return FileKind.DOCX
        except zipfile.BadZipFile:
            return None
    return None


def validate_upload(data: bytes, *, max_bytes: int = DEFAULT_MAX_BYTES) -> FileKind:
    """Return the file's kind, or raise a domain error the API maps to 4xx.

    Size is checked before type so an oversized upload is reported as
    too large, which is the more actionable message, and so we never
    open a zip of arbitrary size just to reject it.
    """

    if len(data) > max_bytes:
        limit_mb = max_bytes / (1024 * 1024)
        raise FileTooLargeError(f"file is larger than the {limit_mb:g} MB limit")
    kind = detect_file_kind(data)
    if kind is None:
        raise UnsupportedFileTypeError("only PDF and DOCX resumes are supported")
    return kind


class TextExtractor(Protocol):
    """Turns validated resume bytes into plain text."""

    def extract(self, data: bytes, kind: FileKind) -> str: ...


class StubTextExtractor:
    """Dependency-free extractor for tests and local development.

    - DOCX: reads paragraph text straight out of `word/document.xml`
      with the standard library. Good enough for simple documents.
    - PDF: real PDF text extraction needs a layout-aware parser, which
      is deliberately not a dependency of this repo. A production
      deployment implements `TextExtractor` with pdfminer.six (PDF) and
      python-docx (DOCX) and passes it to `ResumeService`. This stub
      treats everything after the `%PDF-` header line as UTF-8 text,
      which is what `StubDocumentRenderer` writes, so exported stub
      files can be uploaded again.
    """

    def extract(self, data: bytes, kind: FileKind) -> str:
        text = self._extract_docx(data) if kind is FileKind.DOCX else self._extract_pdf(data)
        text = text.strip()
        if not text:
            raise ResumeParseError("no readable text found in the file")
        return text

    @staticmethod
    def _extract_pdf(data: bytes) -> str:
        _header, _sep, body = data.partition(b"\n")
        return body.decode("utf-8", errors="ignore")

    @staticmethod
    def _extract_docx(data: bytes) -> str:
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                xml = archive.read(_DOCX_REQUIRED_MEMBER).decode("utf-8", errors="ignore")
        except (zipfile.BadZipFile, KeyError) as exc:
            raise ResumeParseError("could not read the DOCX file") from exc
        xml = re.sub(r"</w:p>", "\n", xml)
        text = re.sub(r"<[^>]+>", "", xml)
        return (
            text.replace("&amp;", "&")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&quot;", '"')
            .replace("&apos;", "'")
        )
