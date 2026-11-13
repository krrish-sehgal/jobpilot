"""Typed shapes for resumes and tailorings.

The public models here (`Resume`, `ResumeSections`, `Tailoring`,
`Suggestion`, `KeywordEntry`) mirror `docs/web-api.md` field for field,
so the web layer can return them directly. The `*Record` subclasses add
the internal columns (owner, storage key, raw text) that must never
leave the server.

Models that an LLM fills in (`ResumeSections`) ignore unknown keys but
are strict about types: a model that returns a string where a list is
expected fails validation, and the caller turns that into a clean
"resume failed to parse" instead of a half-populated resume.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from jobpilot.models import SeniorityBand

# ---------------------------------------------------------------------------
# Resume content
# ---------------------------------------------------------------------------


class Bullet(BaseModel):
    """One achievement line. `id` is assigned by the parser, not the LLM."""

    id: str = ""
    text: str = Field(min_length=1)


class ContactInfo(BaseModel):
    name: str = ""
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    links: list[str] = Field(default_factory=list)


class ExperienceEntry(BaseModel):
    id: str = ""
    company: str
    title: str
    start: str
    end: str | None = None  # None means "present"
    bullets: list[Bullet] = Field(default_factory=list)


class EducationEntry(BaseModel):
    id: str = ""
    institution: str
    degree: str
    start: str | None = None
    end: str | None = None
    score: str | None = None


class ProjectEntry(BaseModel):
    id: str = ""
    name: str
    bullets: list[Bullet] = Field(default_factory=list)
    tech: list[str] = Field(default_factory=list)


class ResumeSections(BaseModel):
    """A parsed resume. This is the unit tailoring reads and rewrites."""

    model_config = ConfigDict(extra="ignore")

    contact: ContactInfo = Field(default_factory=ContactInfo)
    summary: str | None = None
    experience: list[ExperienceEntry] = Field(default_factory=list)
    education: list[EducationEntry] = Field(default_factory=list)
    projects: list[ProjectEntry] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)


class ResumeStatus(StrEnum):
    PARSING = "parsing"
    READY = "ready"
    FAILED = "failed"


class ResumeSummary(BaseModel):
    id: UUID
    file_name: str
    status: ResumeStatus
    is_primary: bool = False
    uploaded_at: datetime


class Resume(ResumeSummary):
    failure_reason: str | None = None
    sections: ResumeSections | None = None


class ResumeRecord(Resume):
    """A resume row including server-only columns."""

    user_id: UUID
    storage_key: str
    raw_text: str | None = None

    def to_public(self) -> Resume:
        return Resume.model_validate(
            self.model_dump(exclude={"user_id", "storage_key", "raw_text"})
        )

    def to_summary(self) -> ResumeSummary:
        return ResumeSummary.model_validate(
            self.model_dump(include=set(ResumeSummary.model_fields))
        )


# ---------------------------------------------------------------------------
# Tailoring
# ---------------------------------------------------------------------------


class KeywordImportance(StrEnum):
    REQUIRED = "required"
    PREFERRED = "preferred"


class KeywordEntry(BaseModel):
    term: str
    importance: KeywordImportance
    found_in_resume: bool = False
    covered_after: bool = False


class SuggestionKind(StrEnum):
    REWRITE_BULLET = "rewrite_bullet"
    REWRITE_SUMMARY = "rewrite_summary"
    ADD_SKILL = "add_skill"
    REORDER_SECTION = "reorder_section"


class SuggestionSection(StrEnum):
    SUMMARY = "summary"
    EXPERIENCE = "experience"
    PROJECTS = "projects"
    SKILLS = "skills"


class Decision(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class Suggestion(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    kind: SuggestionKind
    target_id: str | None = None
    section: SuggestionSection
    original: str | None = None
    proposed: str = Field(min_length=1)
    reason: str = ""
    keywords_added: list[str] = Field(default_factory=list)
    decision: Decision = Decision.PENDING


class TailoringStatus(StrEnum):
    RUNNING = "running"
    READY = "ready"
    FAILED = "failed"


class Tailoring(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    resume_id: UUID
    job_id: UUID | None = None
    job_title: str
    company: str | None = None
    status: TailoringStatus = TailoringStatus.RUNNING
    score_before: float = 0
    score_after: float = 0
    keywords: list[KeywordEntry] = Field(default_factory=list)
    suggestions: list[Suggestion] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TailoringRecord(Tailoring):
    """A tailoring row including the inputs needed to re-score it later."""

    user_id: UUID
    job_description_text: str | None = None
    job_seniority_band: SeniorityBand | None = None
    failure_reason: str | None = None

    def to_public(self) -> Tailoring:
        return Tailoring.model_validate(
            self.model_dump(
                exclude={"user_id", "job_description_text", "job_seniority_band", "failure_reason"}
            )
        )
