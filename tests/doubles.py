"""In-memory test doubles for the resume file boundaries.

They need no PDF or Word libraries: the "PDF" is the `%PDF-` header
followed by plain text, and the "DOCX" is a minimal OOXML package. The
two classes round-trip each other, so exported files can be uploaded.
"""

from __future__ import annotations

import io
import re
import zipfile
from html import escape

from jobpilot.errors import ResumeParseError
from jobpilot.resume.extract import FileKind
from jobpilot.resume.models import ResumeSections
from jobpilot.resume.render import DocumentFormat, RenderedDocument, render_text

_DOCX_MEMBER = "word/document.xml"


class PlainTextExtractor:
    """Test double for `TextExtractor`.

    - DOCX: reads paragraph text straight out of `word/document.xml`.
    - PDF: treats everything after the `%PDF-` header line as UTF-8 text.
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
                xml = archive.read(_DOCX_MEMBER).decode("utf-8", errors="ignore")
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


class PlainTextRenderer:
    """Test double for `DocumentRenderer`: PDF is header + plain text."""

    def render(self, sections: ResumeSections, fmt: DocumentFormat) -> RenderedDocument:
        text = render_text(sections)
        if fmt is DocumentFormat.PDF:
            return RenderedDocument(b"%PDF-1.4\n" + text.encode("utf-8"), "application/pdf", "pdf")
        return RenderedDocument(
            _minimal_docx(text),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "docx",
        )


_CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/'
    'package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.'
    'openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="'
    'application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.'
    'openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>'
)
_RELS = (
    '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.'
    'openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://'
    'schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
    'Target="word/document.xml"/></Relationships>'
)


def _minimal_docx(text: str) -> bytes:
    paragraphs = "".join(
        f'<w:p><w:r><w:t xml:space="preserve">{escape(line)}</w:t></w:r></w:p>'
        for line in text.splitlines()
    )
    document = (
        '<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="http://schemas.'
        f'openxmlformats.org/wordprocessingml/2006/main"><w:body>{paragraphs}</w:body></w:document>'
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _CONTENT_TYPES)
        archive.writestr("_rels/.rels", _RELS)
        archive.writestr("word/document.xml", document)
    return buffer.getvalue()
