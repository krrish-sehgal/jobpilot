"""Render a `ResumeSections` as an ATS-friendly document.

Applicant tracking systems parse text, in reading order. So the HTML
here is one column, built from headings, paragraphs and lists: no
tables, no multi-column layout, no images, no text in headers or
footers, standard section names. Looking plain is the feature.

Turning that into a PDF or DOCX file needs a layout engine, which is not
a dependency of this repo, so export sits behind `DocumentRenderer`. A
deployment plugs in HTML-to-PDF (WeasyPrint or headless Chromium over
`render_html`) and python-docx; `StubDocumentRenderer` produces minimal
files for tests and local development.
"""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass
from enum import StrEnum
from html import escape
from typing import Protocol

from jobpilot.resume.models import ResumeSections

_STYLE = """
body{font-family:Arial,Helvetica,sans-serif;font-size:11pt;line-height:1.35;
max-width:7.5in;margin:0 auto;color:#111}
h1{font-size:20pt;margin:0 0 2pt}h2{font-size:12pt;text-transform:uppercase;
border-bottom:1px solid #999;margin:14pt 0 4pt;padding-bottom:2pt}
h3{font-size:11pt;margin:8pt 0 0}ul{margin:2pt 0 0 18pt;padding:0}p{margin:2pt 0}
.meta{color:#444}
""".strip()


def _date_range(start: str | None, end: str | None, *, current: bool = False) -> str:
    if not start and not end:
        return ""
    return f"{start or ''} – {end or ('Present' if current else '')}".strip(" –")


def _bullets(items: list[str]) -> str:
    if not items:
        return ""
    return "<ul>" + "".join(f"<li>{escape(i)}</li>" for i in items) + "</ul>"


def render_html(sections: ResumeSections) -> str:
    """Single-column HTML for `sections`. All text is escaped."""

    contact = sections.contact
    contact_line = " | ".join(
        escape(x) for x in [contact.email, contact.phone, contact.location, *contact.links] if x
    )
    parts = [f"<h1>{escape(contact.name)}</h1>", f'<p class="meta">{contact_line}</p>']

    if sections.summary:
        parts += ["<h2>Summary</h2>", f"<p>{escape(sections.summary)}</p>"]
    if sections.experience:
        parts.append("<h2>Experience</h2>")
        for job in sections.experience:
            dates = _date_range(job.start, job.end, current=True)
            parts.append(f"<h3>{escape(job.title)}, {escape(job.company)}</h3>")
            parts.append(f'<p class="meta">{escape(dates)}</p>')
            parts.append(_bullets([b.text for b in job.bullets]))
    if sections.projects:
        parts.append("<h2>Projects</h2>")
        for project in sections.projects:
            tech = f" ({escape(', '.join(project.tech))})" if project.tech else ""
            parts.append(f"<h3>{escape(project.name)}{tech}</h3>")
            parts.append(_bullets([b.text for b in project.bullets]))
    if sections.education:
        parts.append("<h2>Education</h2>")
        for edu in sections.education:
            parts.append(f"<h3>{escape(edu.degree)}, {escape(edu.institution)}</h3>")
            detail = " | ".join(x for x in [_date_range(edu.start, edu.end), edu.score or ""] if x)
            if detail:
                parts.append(f'<p class="meta">{escape(detail)}</p>')
    if sections.skills:
        parts += ["<h2>Skills</h2>", f"<p>{escape(', '.join(sections.skills))}</p>"]

    body = "\n".join(p for p in parts if p)
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        f"<title>{escape(contact.name)} - Resume</title><style>{_STYLE}</style></head>"
        f"<body>\n{body}\n</body></html>"
    )


def render_text(sections: ResumeSections) -> str:
    """Plain-text rendering, one line per paragraph or bullet."""

    c = sections.contact
    lines = [c.name, " | ".join(x for x in [c.email, c.phone, c.location, *c.links] if x), ""]
    if sections.summary:
        lines += ["SUMMARY", sections.summary, ""]
    if sections.experience:
        lines.append("EXPERIENCE")
        for job in sections.experience:
            lines.append(
                f"{job.title}, {job.company} ({_date_range(job.start, job.end, current=True)})"
            )
            lines += [f"- {b.text}" for b in job.bullets]
        lines.append("")
    if sections.projects:
        lines.append("PROJECTS")
        for project in sections.projects:
            lines.append(project.name + (f" ({', '.join(project.tech)})" if project.tech else ""))
            lines += [f"- {b.text}" for b in project.bullets]
        lines.append("")
    if sections.education:
        lines.append("EDUCATION")
        for edu in sections.education:
            extra = " ".join(x for x in [_date_range(edu.start, edu.end), edu.score or ""] if x)
            lines.append(f"{edu.degree}, {edu.institution}" + (f" ({extra})" if extra else ""))
        lines.append("")
    if sections.skills:
        lines += ["SKILLS", ", ".join(sections.skills)]
    return "\n".join(lines).strip() + "\n"


class DocumentFormat(StrEnum):
    PDF = "pdf"
    DOCX = "docx"


@dataclass(frozen=True)
class RenderedDocument:
    content: bytes
    media_type: str
    extension: str


class DocumentRenderer(Protocol):
    def render(self, sections: ResumeSections, fmt: DocumentFormat) -> RenderedDocument: ...


class StubDocumentRenderer:
    """Minimal renderer for tests and local development.

    - DOCX: a genuine, minimal OOXML package (one paragraph per line)
      that Word and LibreOffice open.
    - PDF: NOT a laid-out PDF. It is the `%PDF-` header followed by the
      plain text, which is what `StubTextExtractor` reads back. A real
      renderer replaces this class; callers only see the protocol.
    """

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
