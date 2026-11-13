from __future__ import annotations

from uuid import uuid4

import pytest

from jobpilot.db.repositories.jobs import JobRepository
from jobpilot.db.repositories.resumes import ResumeRepository
from jobpilot.db.repositories.tailorings import TailoringRepository
from jobpilot.errors import (
    FileTooLargeError,
    RecordNotFoundError,
    RequestRejectedError,
    ResumeNotReadyError,
    TailoringNotReadyError,
    UnsupportedFileTypeError,
)
from jobpilot.integrations.storage import InMemoryObjectStorage
from jobpilot.integrations.supabase_client import InMemoryDatabase
from jobpilot.models import SeniorityBand
from jobpilot.resume.models import ResumeStatus, TailoringStatus
from jobpilot.resume.render import DocumentFormat
from jobpilot.resume.service import ResumeService, ServiceResumeFetcher, run_inline
from tests.conftest import make_job_record
from tests.resume_fixtures import make_docx, make_pdf, scripted_llm

SKILL = {
    "kind": "add_skill",
    "section": "skills",
    "proposed": "Jenkins",
    "reason": "Required, and your CI work shows it.",
    "keywords_added": ["jenkins"],
}
INVENTED = {**SKILL, "proposed": "Kubernetes", "keywords_added": ["kubernetes"]}
JOB_KEYWORDS = {"job_title": None, "company": None, "required": ["kubernetes"], "preferred": []}


def make_service(llm=None, *, on_ready=None, max_bytes=1024 * 1024):
    db = InMemoryDatabase()
    jobs = JobRepository(db)
    service = ResumeService(
        resumes=ResumeRepository(db),
        tailorings=TailoringRepository(db),
        jobs=jobs,
        storage=InMemoryObjectStorage(),
        llm=llm or scripted_llm(),
        schedule=run_inline,
        max_bytes=max_bytes,
        on_resume_ready=on_ready,
    )
    return service, jobs


def test_upload_parses_and_first_resume_becomes_primary():
    ready_calls = []
    service, _ = make_service(on_ready=lambda user, sections: ready_calls.append(sections))
    user = uuid4()
    record = service.upload(user, "../../cv.pdf", make_pdf())
    loaded = service.get_resume(user, record.id)
    assert loaded.status is ResumeStatus.READY and loaded.is_primary
    assert loaded.file_name == "cv.pdf"  # path components stripped
    assert loaded.sections.contact.name == "Priya Nair"
    assert ready_calls and ServiceResumeFetcher(service).fetch(user)

    second = service.get_resume(user, service.upload(user, "b.docx", make_docx()).id)
    assert not second.is_primary
    service.set_primary(user, second.id)
    assert service.get_resume(user, second.id).is_primary
    assert not service.get_resume(user, record.id).is_primary


def test_invalid_uploads_fail_synchronously():
    service, _ = make_service(max_bytes=64)
    with pytest.raises(UnsupportedFileTypeError):
        service.upload(uuid4(), "cv.pdf", b"not a pdf")
    with pytest.raises(FileTooLargeError):
        service.upload(uuid4(), "cv.pdf", make_pdf("x" * 200))


def test_unparseable_resume_is_marked_failed_with_a_reason():
    service, _ = make_service(scripted_llm(parse_reply="sorry, I cannot help"))
    user = uuid4()
    record = service.get_resume(user, service.upload(user, "cv.pdf", make_pdf()).id)
    assert record.status is ResumeStatus.FAILED
    assert "JSON" in record.failure_reason
    assert service.primary_resume_text(user) is None
    with pytest.raises(ResumeNotReadyError):
        service.set_primary(user, record.id)
    with pytest.raises(ResumeNotReadyError):
        service.start_tailoring(user, record.id, job_description_text="Python role")


def test_other_users_resumes_are_invisible():
    service, _ = make_service()
    owner = uuid4()
    record = service.upload(owner, "cv.pdf", make_pdf())
    with pytest.raises(RecordNotFoundError):
        service.get_resume(uuid4(), record.id)


def _tailor(service, jobs, llm_keywords=None):
    user = uuid4()
    resume = service.upload(user, "cv.pdf", make_pdf())
    job = jobs.save(
        make_job_record(
            skills=["python", "jenkins", "kubernetes"],
            seniority_band=SeniorityBand.SENIOR,
            min_years_experience=6,
        )
    )
    tailoring = service.start_tailoring(user, resume.id, job_id=job.id)
    return user, job, service.get_tailoring(user, tailoring.id)


def test_tailoring_for_a_job_applies_guard_and_scores():
    llm = scripted_llm(keywords=JOB_KEYWORDS, suggestions=[SKILL, INVENTED])
    service, jobs = make_service(llm)
    _, job, tailoring = _tailor(service, jobs)
    assert tailoring.status is TailoringStatus.READY
    assert tailoring.job_id == job.id and tailoring.job_title == job.title
    assert [s.proposed for s in tailoring.suggestions] == ["Jenkins"]
    assert tailoring.score_after > tailoring.score_before
    assert {e.term for e in tailoring.keywords} >= {"python", "jenkins", "kubernetes"}


def test_tailoring_from_pasted_text_uses_extracted_title():
    llm = scripted_llm(
        keywords={"job_title": "Platform Engineer", "company": "Globex", "required": ["python"]}
    )
    service, _ = make_service(llm)
    user = uuid4()
    resume = service.upload(user, "cv.pdf", make_pdf())
    started = service.start_tailoring(
        user, resume.id, job_description_text="We need a platform engineer."
    )
    assert started.status is TailoringStatus.RUNNING or started.job_title
    done = service.get_tailoring(user, started.id)
    assert (done.job_title, done.company, done.job_id) == ("Platform Engineer", "Globex", None)


def test_exactly_one_job_source_is_required():
    service, _ = make_service()
    user = uuid4()
    resume = service.upload(user, "cv.pdf", make_pdf())
    with pytest.raises(RequestRejectedError):
        service.start_tailoring(user, resume.id)
    with pytest.raises(RequestRejectedError):
        service.start_tailoring(user, resume.id, job_id=uuid4(), job_description_text="x")
    with pytest.raises(RecordNotFoundError):
        service.start_tailoring(user, resume.id, job_id=uuid4())


def test_tailoring_failure_is_recorded_not_raised():
    service, _ = make_service(scripted_llm(keywords={"required": [], "preferred": []}))
    user = uuid4()
    resume = service.upload(user, "cv.pdf", make_pdf())
    started = service.start_tailoring(user, resume.id, job_description_text="Vague posting")
    assert service.get_tailoring(user, started.id).status is TailoringStatus.FAILED
    with pytest.raises(TailoringNotReadyError):
        service.export(user, started.id, DocumentFormat.PDF)


def test_decisions_update_score_and_validate_ids():
    llm = scripted_llm(keywords=JOB_KEYWORDS, suggestions=[SKILL])
    service, jobs = make_service(llm)
    user, _, tailoring = _tailor(service, jobs)
    suggestion = tailoring.suggestions[0]

    rejected = service.decide(user, tailoring.id, accepted=[], rejected=[suggestion.id])
    assert rejected.suggestions[0].decision.value == "rejected"
    assert rejected.score_after == rejected.score_before == tailoring.score_before

    accepted = service.decide(user, tailoring.id, accepted=[suggestion.id], rejected=[])
    assert accepted.suggestions[0].decision.value == "accepted"
    assert accepted.score_after > accepted.score_before

    with pytest.raises(RequestRejectedError):
        service.decide(user, tailoring.id, accepted=[uuid4()], rejected=[])
    with pytest.raises(RequestRejectedError):
        service.decide(user, tailoring.id, accepted=[suggestion.id], rejected=[suggestion.id])


def test_export_contains_only_accepted_changes():
    llm = scripted_llm(keywords=JOB_KEYWORDS, suggestions=[SKILL])
    service, jobs = make_service(llm)
    user, _, tailoring = _tailor(service, jobs)

    original, name = service.export(user, tailoring.id, DocumentFormat.PDF)
    assert b"Jenkins," not in original.content.split(b"SKILLS")[-1]
    assert name == "priya-nair-tailored.pdf"

    service.decide(user, tailoring.id, accepted=[tailoring.suggestions[0].id], rejected=[])
    edited, _ = service.export(user, tailoring.id, DocumentFormat.PDF)
    assert b"Jenkins" in edited.content.split(b"SKILLS")[-1]


def test_start_from_chat_reports_why_it_cannot_start():
    llm = scripted_llm(keywords=JOB_KEYWORDS, suggestions=[SKILL])
    service, jobs = make_service(llm)
    job = jobs.save(make_job_record(skills=["python"]))
    user = uuid4()
    assert service.start_from_chat(user, "garbage")["reason"] == "job_not_found"
    assert service.start_from_chat(user, str(job.id))["reason"] == "no_resume"
    service.upload(user, "cv.pdf", make_pdf())
    result = service.start_from_chat(user, str(job.id))
    assert result["started"] is True and result["job_title"] == job.title
    assert service.get_tailoring(user, result["tailoring_id"]).status is TailoringStatus.READY
