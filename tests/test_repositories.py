from __future__ import annotations

from uuid import uuid4

import pytest

from jobpilot.db.repositories.jobs import JobRepository
from jobpilot.errors import RecordNotFoundError
from jobpilot.integrations.supabase_client import InMemoryDatabase
from tests.conftest import make_job_record


def test_job_repository_save_and_get_round_trip():
    repo = JobRepository(InMemoryDatabase())
    job = make_job_record()
    repo.save(job)
    fetched = repo.get(job.id)
    assert fetched.title == job.title
    assert fetched.id == job.id


def test_job_repository_get_missing_raises():
    repo = JobRepository(InMemoryDatabase())
    with pytest.raises(RecordNotFoundError):
        repo.get(uuid4())


def test_job_repository_find_by_content_hash():
    repo = JobRepository(InMemoryDatabase())
    job = make_job_record()
    repo.save(job)
    found = repo.find_by_content_hash(job.content_hash)
    assert found is not None
    assert found.id == job.id
    assert repo.find_by_content_hash("does-not-exist") is None


def test_job_repository_find_by_role_category():
    from jobpilot.models import RoleCategory

    repo = JobRepository(InMemoryDatabase())
    eng = make_job_record(role_category=RoleCategory.SOFTWARE_ENGINEERING)
    sales = make_job_record(role_category=RoleCategory.SALES_AND_BUSINESS_DEV)
    repo.save(eng)
    repo.save(sales)
    result = repo.find_by_role_category(RoleCategory.SOFTWARE_ENGINEERING.value)
    assert [j.id for j in result] == [eng.id]


def test_job_repository_delete_is_idempotent():
    repo = JobRepository(InMemoryDatabase())
    job = make_job_record()
    repo.save(job)
    repo.delete(job.id)
    with pytest.raises(RecordNotFoundError):
        repo.get(job.id)
    repo.delete(job.id)  # deleting again should not raise
