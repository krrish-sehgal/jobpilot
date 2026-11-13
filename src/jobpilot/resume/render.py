"""Render a `ResumeSections` as an ATS-friendly document.

Applicant tracking systems parse text, in reading order. So the HTML
here is one column, built from headings, paragraphs and lists: no
tables, no multi-column layout, no images, no text in headers or
footers, standard section names. Looking plain is the feature.

Export sits behind the `DocumentRenderer` protocol;
`FileDocumentRenderer` produces the PDF (WeasyPrint over `render_html`)
and DOCX (python-docx) files.
"""

from __future__ import annotations

import io
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


_DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class FileDocumentRenderer:
    """Renders resumes to real files.

    - PDF: WeasyPrint over `render_html`, so the file has a selectable
      text layer in reading order.
    - DOCX: python-docx, using the built-in heading and list styles.

    Both libraries are imported when first used.
    """

    def render(self, sections: ResumeSections, fmt: DocumentFormat) -> RenderedDocument:
        if fmt is DocumentFormat.PDF:
            return RenderedDocument(self._pdf(sections), "application/pdf", "pdf")
        return RenderedDocument(self._docx(sections), _DOCX_MEDIA_TYPE, "docx")

    @staticmethod
    def _pdf(sections: ResumeSections) -> bytes:
        from weasyprint import HTML

        return HTML(string=render_html(sections)).write_pdf()

    @staticmethod
    def _docx(sections: ResumeSections) -> bytes:
        from docx import Document

        doc = Document()
        contact = sections.contact
        doc.add_heading(contact.name or "Resume", level=0)
        details = " | ".join(
            x for x in [contact.email, contact.phone, contact.location, *contact.links] if x
        )
        if details:
            doc.add_paragraph(details)

        def bullets(items: list[str]) -> None:
            for item in items:
                doc.add_paragraph(item, style="List Bullet")

        if sections.summary:
            doc.add_heading("Summary", level=1)
            doc.add_paragraph(sections.summary)
        if sections.experience:
            doc.add_heading("Experience", level=1)
            for job in sections.experience:
                doc.add_heading(f"{job.title}, {job.company}", level=2)
                dates = _date_range(job.start, job.end, current=True)
                if dates:
                    doc.add_paragraph(dates)
                bullets([b.text for b in job.bullets])
        if sections.projects:
            doc.add_heading("Projects", level=1)
            for project in sections.projects:
                tech = f" ({', '.join(project.tech)})" if project.tech else ""
                doc.add_heading(f"{project.name}{tech}", level=2)
                bullets([b.text for b in project.bullets])
        if sections.education:
            doc.add_heading("Education", level=1)
            for edu in sections.education:
                doc.add_heading(f"{edu.degree}, {edu.institution}", level=2)
                detail = " | ".join(
                    x for x in [_date_range(edu.start, edu.end), edu.score or ""] if x
                )
                if detail:
                    doc.add_paragraph(detail)
        if sections.skills:
            doc.add_heading("Skills", level=1)
            doc.add_paragraph(", ".join(sections.skills))

        buffer = io.BytesIO()
        doc.save(buffer)
        return buffer.getvalue()
