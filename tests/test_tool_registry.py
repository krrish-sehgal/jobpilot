from __future__ import annotations

from uuid import uuid4

import pytest

from jobpilot.agent.registry import build_default_registry
from jobpilot.agent.tools import AgentToolContext, StaticResumeFetcher
from jobpilot.db.repositories.jobs import JobRepository
from jobpilot.db.repositories.users import UserFactRepository
from jobpilot.errors import ToolArgumentError, UnknownToolError
from jobpilot.integrations.llm import FakeLLMClient
from jobpilot.integrations.supabase_client import InMemoryDatabase
from jobpilot.memory.store import MemoryStore
from tests.conftest import make_job_record


def build_context(user_id=None) -> AgentToolContext:
    db = InMemoryDatabase()
    llm = FakeLLMClient()
    jobs = JobRepository(db)
    memory = MemoryStore(llm, UserFactRepository(db))
    resumes = StaticResumeFetcher(resumes_by_user_id={})
    return AgentToolContext(
        user_id=user_id or uuid4(),
        conversation_id=uuid4(),
        llm=llm,
        job_repository=jobs,
        memory_store=memory,
        resume_fetcher=resumes,
    ), jobs


def test_registry_exposes_all_four_tool_schemas():
    registry = build_default_registry()
    assert set(registry.names()) == {
        "search_jobs",
        "recall_memory",
        "fetch_resume",
        "get_job_details",
    }
    for schema in registry.schemas():
        assert "name" in schema and "input_schema" in schema


def test_invoke_unknown_tool_raises():
    registry = build_default_registry()
    ctx, _ = build_context()
    with pytest.raises(UnknownToolError):
        registry.invoke(ctx, "delete_everything", {})


def test_invoke_with_invalid_arguments_raises():
    registry = build_default_registry()
    ctx, _ = build_context()
    with pytest.raises(ToolArgumentError):
        registry.invoke(ctx, "search_jobs", {"limit": 3})  # missing required "query"


def test_search_jobs_returns_matches(monkeypatch):
    registry = build_default_registry()
    ctx, jobs = build_context()
    job = make_job_record()
    jobs.save(job)
    result = registry.invoke(ctx, "search_jobs", {"query": job.candidate_profile_text, "limit": 5})
    assert isinstance(result, list)
    assert result
    assert result[0]["title"] == job.title


def test_get_job_details_found_and_not_found():
    registry = build_default_registry()
    ctx, jobs = build_context()
    job = make_job_record()
    jobs.save(job)

    found = registry.invoke(ctx, "get_job_details", {"job_id": str(job.id)})
    assert found["found"] is True
    assert found["title"] == job.title

    not_found = registry.invoke(ctx, "get_job_details", {"job_id": str(uuid4())})
    assert not_found["found"] is False


def test_fetch_resume_found_and_missing():
    registry = build_default_registry()
    user_id = uuid4()
    db = InMemoryDatabase()
    llm = FakeLLMClient()
    jobs = JobRepository(db)
    memory = MemoryStore(llm, UserFactRepository(db))
    ctx_with_resume = AgentToolContext(
        user_id=user_id,
        conversation_id=uuid4(),
        llm=llm,
        job_repository=jobs,
        memory_store=memory,
        resume_fetcher=StaticResumeFetcher(resumes_by_user_id={str(user_id): "resume text"}),
    )
    result = registry.invoke(ctx_with_resume, "fetch_resume", {})
    assert result == {"found": True, "resume_text": "resume text"}

    ctx_without, _ = build_context()
    result_missing = registry.invoke(ctx_without, "fetch_resume", {})
    assert result_missing == {"found": False, "resume_text": None}
