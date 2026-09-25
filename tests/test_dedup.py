from __future__ import annotations

import pytest

from jobpilot.errors import DuplicatePostingError
from jobpilot.ingest.dedup import Deduplicator
from jobpilot.models import RawPosting
from jobpilot.utils.hashing import content_hash, normalize_for_hashing


def make_posting(
    title="Backend Engineer", company="Acme", description="Build things."
) -> RawPosting:
    return RawPosting(
        source_platform="talentflow",
        source_listing_id="123",
        title=title,
        company=company,
        description=description,
        apply_url="https://apply.example.com/1",
        content_hash=content_hash(title, company, description),
    )


def test_normalize_for_hashing_collapses_whitespace_and_case():
    assert normalize_for_hashing("  Hello   WORLD!  ") == "hello world"


def test_content_hash_stable_for_equivalent_text():
    a = content_hash("Backend Engineer", "Acme", "Build things.")
    b = content_hash("backend engineer", "ACME", "build   things")
    assert a == b


def test_content_hash_differs_for_different_content():
    a = content_hash("Backend Engineer", "Acme", "Build things.")
    b = content_hash("Frontend Engineer", "Acme", "Build things.")
    assert a != b


def test_deduplicator_flags_repeat_within_a_run(job_repository):
    dedup = Deduplicator(job_repository)
    posting = make_posting()
    dedup.check(posting)
    dedup.mark_seen(posting)
    with pytest.raises(DuplicatePostingError):
        dedup.check(posting)


def test_deduplicator_flags_repeat_across_runs(job_repository):
    from tests.conftest import make_job_record

    posting = make_posting()
    existing = make_job_record().model_copy(update={"content_hash": posting.content_hash})
    job_repository.save(existing)

    dedup = Deduplicator(job_repository)
    with pytest.raises(DuplicatePostingError):
        dedup.check(posting)


def test_deduplicator_is_duplicate_helper(job_repository):
    dedup = Deduplicator(job_repository)
    posting = make_posting()
    assert dedup.is_duplicate(posting) is False
    dedup.mark_seen(posting)
    assert dedup.is_duplicate(posting) is True
