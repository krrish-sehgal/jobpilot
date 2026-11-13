"""Shared builders for the resume tailoring tests."""

from __future__ import annotations

import io
import json
import zipfile

from jobpilot.resume.models import ResumeSections
from jobpilot.resume.parser import assign_ids

SAMPLE_RESUME_PAYLOAD: dict = {
    "contact": {
        "name": "Priya Nair",
        "email": "priya@example.com",
        "phone": None,
        "location": "Bengaluru",
        "links": [],
    },
    "summary": "Backend engineer with experience building Python services on AWS.",
    "experience": [
        {
            "company": "Acme Payments",
            "title": "Backend Engineer",
            "start": "Jan 2022",
            "end": None,
            "bullets": [
                {
                    "text": "Built a payment reconciliation service in Python and "
                    "PostgreSQL processing 2 million transactions daily"
                },
                {"text": "Reduced API latency by 35% by adding Redis caching"},
                {"text": "Mentored 3 junior engineers"},
            ],
        },
        {
            "company": "Bright Labs",
            "title": "Software Engineer",
            "start": "Jun 2019",
            "end": "Dec 2021",
            "bullets": [
                {"text": "Developed REST APIs with Flask used by 12 internal teams"},
                {"text": "Wrote CI pipelines in Jenkins and deployed services with Docker"},
            ],
        },
    ],
    "education": [
        {
            "institution": "IIT Madras",
            "degree": "B.Tech Computer Science",
            "start": "2015",
            "end": "2019",
            "score": "8.4 CGPA",
        }
    ],
    "projects": [
        {
            "name": "Log Search",
            "bullets": [{"text": "Built a log search tool with Elasticsearch"}],
            "tech": ["Elasticsearch", "Python"],
        }
    ],
    "skills": ["Python", "Flask", "PostgreSQL", "AWS", "Docker"],
}


def sample_sections() -> ResumeSections:
    """The sample resume, parsed and with stable ids assigned."""

    return assign_ids(ResumeSections.model_validate(SAMPLE_RESUME_PAYLOAD))


def sample_resume_json() -> str:
    return json.dumps(SAMPLE_RESUME_PAYLOAD)


SAMPLE_RESUME_TEXT = "Priya Nair\npriya@example.com\nBackend Engineer, Acme Payments\n"


def make_pdf(text: str = SAMPLE_RESUME_TEXT) -> bytes:
    """A file that passes the PDF magic-byte check and the stub extractor."""

    return b"%PDF-1.4\n" + text.encode("utf-8")


def make_docx(paragraphs: list[str] | None = None) -> bytes:
    paragraphs = paragraphs or SAMPLE_RESUME_TEXT.splitlines()
    body = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs)
    xml = f'<w:document xmlns:w="x"><w:body>{body}</w:body></w:document>'
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", xml)
    return buffer.getvalue()
