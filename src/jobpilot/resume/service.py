"""`ResumeService`: the application service behind the resume endpoints.

It owns the workflow and nothing else: validate an upload, store the
bytes, parse in the background, start a tailoring, apply the user's
decisions, export. Parsing, scoring, the guard and rendering live in
their own modules and are injected or called here, so each can be tested
without this orchestration (and this orchestration without them).

Two steps are slow (an LLM parse, an LLM tailoring), so they run through
an injected `Scheduler`. Production uses `run_in_thread`; tests pass
`run_inline` and get deterministic results with no sleeping.
"""

from __future__ import annotations

import re
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import PurePath
from typing import Any
from uuid import UUID, uuid4

from jobpilot.agent.tools import ResumeFetcher
from jobpilot.db.repositories.jobs import JobRepository
from jobpilot.db.repositories.resumes import ResumeRepository
from jobpilot.db.repositories.tailorings import TailoringRepository
from jobpilot.errors import (
    JobPilotError,
    RecordNotFoundError,
    RequestRejectedError,
    ResumeError,
    ResumeNotReadyError,
    TailoringNotReadyError,
)
from jobpilot.integrations.llm import LLMClient
from jobpilot.integrations.storage import ObjectStorage
from jobpilot.logging import get_logger
from jobpilot.resume.apply import apply_decisions
from jobpilot.resume.extract import (
    DEFAULT_MAX_BYTES,
    StubTextExtractor,
    TextExtractor,
    detect_file_kind,
    validate_upload,
)
from jobpilot.resume.keywords import extract_job_keywords
from jobpilot.resume.models import (
    Decision,
    ResumeRecord,
    ResumeSections,
    ResumeStatus,
    TailoringRecord,
    TailoringStatus,
)
from jobpilot.resume.parser import parse_resume
from jobpilot.resume.render import (
    DocumentFormat,
    DocumentRenderer,
    RenderedDocument,
    StubDocumentRenderer,
)
from jobpilot.resume.tailor import rescore, tailor_resume

logger = get_logger(__name__)

Scheduler = Callable[[Callable[[], None]], None]

PASTED_JOB_TITLE = "Pasted job description"


def run_in_thread(job: Callable[[], None]) -> None:
    """Run `job` on a daemon thread. Fine for one process; a multi-node
    deployment would enqueue to the same queue the ingest workers use."""

    threading.Thread(target=job, daemon=True, name="resume-job").start()


def run_inline(job: Callable[[], None]) -> None:
    """Run `job` immediately on the caller's thread (tests)."""

    job()


def _safe_file_name(name: str) -> str:
    base = PurePath(name.replace("\\", "/")).name.strip()
    return re.sub(r"[^\w.\- ()]", "_", base)[:200] or "resume"


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.casefold()).strip("-") or "resume"


class ResumeService:
    def __init__(
        self,
        *,
        resumes: ResumeRepository,
        tailorings: TailoringRepository,
        jobs: JobRepository,
        storage: ObjectStorage,
        llm: LLMClient,
        extractor: TextExtractor | None = None,
        renderer: DocumentRenderer | None = None,
        max_bytes: int = DEFAULT_MAX_BYTES,
        schedule: Scheduler = run_in_thread,
        on_resume_ready: Callable[[UUID, ResumeSections], None] | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._resumes = resumes
        self._tailorings = tailorings
        self._jobs = jobs
        self._storage = storage
        self._llm = llm
        self._extractor = extractor or StubTextExtractor()
        self._renderer = renderer or StubDocumentRenderer()
        self._max_bytes = max_bytes
        self._schedule = schedule
        self._on_resume_ready = on_resume_ready
        self._clock = clock

    # --- resumes ---------------------------------------------------------

    def upload(self, user_id: UUID, file_name: str, data: bytes) -> ResumeRecord:
        """Validate, store, and start parsing. Returns the `parsing` record.

        Validation errors (`FileTooLargeError`, `UnsupportedFileTypeError`)
        are raised synchronously so the client gets an immediate 4xx
        instead of a resume that silently fails later.
        """

        validate_upload(data, max_bytes=self._max_bytes)
        resume_id = uuid4()
        storage_key = f"resumes/{user_id}/{resume_id}"
        self._storage.put(storage_key, data)
        record = self._resumes.save(
            ResumeRecord(
                id=resume_id,
                user_id=user_id,
                file_name=_safe_file_name(file_name),
                storage_key=storage_key,
                status=ResumeStatus.PARSING,
                uploaded_at=self._clock(),
            )
        )
        self._schedule(lambda: self._parse(user_id, resume_id))
        return record

    def _parse(self, user_id: UUID, resume_id: UUID) -> None:
        record = self._resumes.get_for_user(user_id, resume_id)
        try:
            data = self._storage.get(record.storage_key)
            kind = detect_file_kind(data)
            if kind is None:  # storage returned something other than we stored
                raise ResumeError("the stored file is no longer a readable PDF or DOCX")
            text = self._extractor.extract(data, kind)
            sections = parse_resume(self._llm, text)
        except Exception as exc:
            reason = str(exc) if isinstance(exc, ResumeError) else "processing failed, try again"
            if not isinstance(exc, JobPilotError):
                logger.exception("resume_parse_crashed", resume_id=str(resume_id))
            self._resumes.update(
                record.model_copy(update={"status": ResumeStatus.FAILED, "failure_reason": reason})
            )
            return

        ready = self._resumes.update(
            record.model_copy(
                update={"status": ResumeStatus.READY, "raw_text": text, "sections": sections}
            )
        )
        if self._resumes.primary_for_user(user_id) is None:
            self._resumes.make_primary(user_id, ready.id)
        if self._on_resume_ready is not None:
            try:
                self._on_resume_ready(user_id, sections)
            except Exception:
                logger.exception("on_resume_ready_failed", resume_id=str(resume_id))

    def list_resumes(self, user_id: UUID) -> list[ResumeRecord]:
        return self._resumes.list_for_user(user_id)

    def get_resume(self, user_id: UUID, resume_id: UUID) -> ResumeRecord:
        return self._resumes.get_for_user(user_id, resume_id)

    def has_resume(self, user_id: UUID) -> bool:
        return bool(self._resumes.list_for_user(user_id))

    def set_primary(self, user_id: UUID, resume_id: UUID) -> None:
        record = self._resumes.get_for_user(user_id, resume_id)
        if record.status is not ResumeStatus.READY:
            raise ResumeNotReadyError("only a parsed resume can be made primary")
        self._resumes.make_primary(user_id, resume_id)

    def primary_resume_text(self, user_id: UUID) -> str | None:
        primary = self._resumes.primary_for_user(user_id)
        return primary.raw_text if primary and primary.status is ResumeStatus.READY else None

    # --- tailoring -------------------------------------------------------

    def start_tailoring(
        self,
        user_id: UUID,
        resume_id: UUID,
        *,
        job_id: UUID | None = None,
        job_description_text: str | None = None,
    ) -> TailoringRecord:
        """Create a `running` tailoring and schedule the work."""

        if (job_id is None) == (not job_description_text):
            raise RequestRejectedError("provide exactly one of job_id or job_description_text")
        resume = self._resumes.get_for_user(user_id, resume_id)
        if resume.status is not ResumeStatus.READY:
            raise ResumeNotReadyError("this resume has not finished parsing")

        title, company = PASTED_JOB_TITLE, None
        if job_id is not None:
            job = self._jobs.get(job_id)  # RecordNotFoundError -> 404
            title, company = job.title, job.company
        record = self._tailorings.save(
            TailoringRecord(
                user_id=user_id,
                resume_id=resume_id,
                job_id=job_id,
                job_title=title,
                company=company,
                job_description_text=job_description_text.strip() if job_description_text else None,
                created_at=self._clock(),
            )
        )
        self._schedule(lambda: self._run_tailoring(user_id, record.id))
        return record

    def start_from_chat(self, user_id: UUID, job_id: str) -> dict[str, Any]:
        """Entry point for the agent's `tailor_resume` tool.

        Returns a small result dict instead of raising, because the
        agent should read "you have no resume yet" and say so, not see
        a stack trace.
        """

        try:
            job_uuid = UUID(job_id)
            self._jobs.get(job_uuid)
        except (ValueError, RecordNotFoundError):
            return {"started": False, "reason": "job_not_found"}
        primary = self._resumes.primary_for_user(user_id)
        if primary is None:
            return {"started": False, "reason": "no_resume"}
        try:
            record = self.start_tailoring(user_id, primary.id, job_id=job_uuid)
        except ResumeNotReadyError:
            return {"started": False, "reason": "resume_not_ready"}
        return {
            "started": True,
            "tailoring_id": str(record.id),
            "job_id": job_id,
            "job_title": record.job_title,
            "company": record.company,
        }

    def _run_tailoring(self, user_id: UUID, tailoring_id: UUID) -> None:
        record = self._tailorings.get_for_user(user_id, tailoring_id)
        try:
            resume = self._resumes.get_for_user(user_id, record.resume_id)
            if resume.sections is None:
                raise ResumeNotReadyError("the resume has no parsed content")
            title, company, description, skills, band = (
                record.job_title,
                record.company,
                "",
                [],
                None,
            )
            if record.job_id is not None:
                job = self._jobs.get(record.job_id)
                title, company, description = job.title, job.company, job.description
                skills, band = job.skills, job.seniority_band
            else:
                description = record.job_description_text or ""
            keywords = extract_job_keywords(
                self._llm, title=title, description=description, skills=skills
            )
            if record.job_id is None:
                title, company = keywords.job_title or title, keywords.company
            outcome = tailor_resume(
                self._llm,
                resume.sections,
                keywords,
                job_title=title,
                company=company,
                job_band=band,
            )
            updated = record.model_copy(
                update={
                    "status": TailoringStatus.READY,
                    "job_title": title,
                    "company": company,
                    "job_seniority_band": band,
                    "keywords": outcome.keywords,
                    "suggestions": outcome.suggestions,
                    "score_before": outcome.score_before,
                    "score_after": outcome.score_after,
                }
            )
        except Exception as exc:
            if not isinstance(exc, JobPilotError):
                logger.exception("tailoring_crashed", tailoring_id=str(tailoring_id))
            reason = str(exc) if isinstance(exc, ResumeError) else "tailoring failed, try again"
            updated = record.model_copy(
                update={"status": TailoringStatus.FAILED, "failure_reason": reason}
            )
        self._tailorings.update(updated)

    def get_tailoring(self, user_id: UUID, tailoring_id: UUID) -> TailoringRecord:
        return self._tailorings.get_for_user(user_id, tailoring_id)

    def decide(
        self, user_id: UUID, tailoring_id: UUID, *, accepted: list[UUID], rejected: list[UUID]
    ) -> TailoringRecord:
        """Record accept/reject choices and refresh the potential score.

        Ids not mentioned keep their current decision, so the UI can send
        one change at a time or all at once. Unknown ids, or an id in both
        lists, are rejected outright rather than half-applied.
        """

        record = self._tailorings.get_for_user(user_id, tailoring_id)
        if record.status is not TailoringStatus.READY:
            raise TailoringNotReadyError("this tailoring has no suggestions to decide on")
        known = {s.id for s in record.suggestions}
        if set(accepted) & set(rejected):
            raise RequestRejectedError("a suggestion cannot be both accepted and rejected")
        if not (set(accepted) | set(rejected)) <= known:
            raise RequestRejectedError("unknown suggestion id")

        decisions = {sid: Decision.ACCEPTED for sid in accepted}
        decisions |= {sid: Decision.REJECTED for sid in rejected}
        self._tailorings.set_decisions(tailoring_id, decisions)

        record = self._tailorings.get_for_user(user_id, tailoring_id)
        resume = self._resumes.get_for_user(user_id, record.resume_id)
        assert resume.sections is not None  # a READY tailoring implies a parsed resume
        keywords, _before, after = rescore(
            resume.sections, record.keywords, record.suggestions, record.job_seniority_band
        )
        return self._tailorings.update(
            record.model_copy(update={"keywords": keywords, "score_after": after})
        )

    def export(
        self, user_id: UUID, tailoring_id: UUID, fmt: DocumentFormat
    ) -> tuple[RenderedDocument, str]:
        """Render the resume with accepted suggestions applied.

        With nothing accepted this is simply the original resume in the
        requested format.
        """

        record = self._tailorings.get_for_user(user_id, tailoring_id)
        if record.status is not TailoringStatus.READY:
            raise TailoringNotReadyError("this tailoring is not ready to export")
        resume = self._resumes.get_for_user(user_id, record.resume_id)
        assert resume.sections is not None
        final = apply_decisions(resume.sections, record.suggestions)
        document = self._renderer.render(final, fmt)
        file_name = f"{_slug(final.contact.name)}-tailored.{document.extension}"
        return document, file_name


class ServiceResumeFetcher(ResumeFetcher):
    """Adapts `ResumeService` to the agent's `fetch_resume` tool."""

    def __init__(self, service: ResumeService) -> None:
        self._service = service

    def fetch(self, user_id: UUID) -> str | None:
        return self._service.primary_resume_text(user_id)
