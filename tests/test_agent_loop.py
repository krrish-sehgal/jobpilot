from __future__ import annotations

from uuid import uuid4

import pytest

from jobpilot.agent.loop import AgentLoop
from jobpilot.agent.registry import build_default_registry
from jobpilot.agent.tools import AgentToolContext, StaticResumeFetcher
from jobpilot.db.repositories.jobs import JobRepository
from jobpilot.db.repositories.users import UserFactRepository
from jobpilot.errors import TurnBudgetExceededError
from jobpilot.integrations.llm import FakeLLMClient
from jobpilot.integrations.supabase_client import InMemoryDatabase
from jobpilot.memory.store import MemoryStore
from tests.conftest import make_job_record


def build_context(llm: FakeLLMClient) -> AgentToolContext:
    db = InMemoryDatabase()
    jobs = JobRepository(db)
    jobs.save(make_job_record())
    memory = MemoryStore(llm, UserFactRepository(db))
    return AgentToolContext(
        user_id=uuid4(),
        conversation_id=uuid4(),
        llm=llm,
        job_repository=jobs,
        memory_store=memory,
        resume_fetcher=StaticResumeFetcher(resumes_by_user_id={}),
    )


def test_agent_loop_answers_directly_with_no_tool_calls():
    def responder(system_prompt, messages):
        return {"content": "Hi, how can I help?", "tool_calls": [], "finish_reason": "stop"}

    llm = FakeLLMClient(responder=responder)
    loop = AgentLoop(llm=llm, registry=build_default_registry(), max_turns=3)
    ctx = build_context(llm)

    turn = loop.run(ctx, "hello")
    assert turn.completed is True
    assert turn.final_reply == "Hi, how can I help?"
    assert turn.turns_used == 1
    assert turn.tool_calls == []


def test_agent_loop_calls_a_tool_then_answers():
    call_count = {"n": 0}

    def responder(system_prompt, messages):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return {
                "content": None,
                "tool_calls": [{"name": "search_jobs", "arguments": {"query": "backend engineer"}}],
                "finish_reason": "tool_use",
            }
        return {"content": "Found a great match.", "tool_calls": [], "finish_reason": "stop"}

    llm = FakeLLMClient(responder=responder)
    loop = AgentLoop(llm=llm, registry=build_default_registry(), max_turns=3)
    ctx = build_context(llm)

    turn = loop.run(ctx, "find me a backend job")
    assert turn.completed is True
    assert turn.final_reply == "Found a great match."
    assert len(turn.tool_calls) == 1
    assert turn.tool_calls[0].name == "search_jobs"
    assert turn.tool_calls[0].error is None


def test_agent_loop_raises_when_turn_budget_exceeded():
    def responder(system_prompt, messages):
        return {
            "content": None,
            "tool_calls": [{"name": "search_jobs", "arguments": {"query": "anything"}}],
            "finish_reason": "tool_use",
        }

    llm = FakeLLMClient(responder=responder)
    loop = AgentLoop(llm=llm, registry=build_default_registry(), max_turns=2)
    ctx = build_context(llm)

    with pytest.raises(TurnBudgetExceededError):
        loop.run(ctx, "keep searching forever")


def test_agent_loop_caps_tool_calls_per_turn():
    def responder(system_prompt, messages):
        return {
            "content": "done",
            "tool_calls": [
                {"name": "search_jobs", "arguments": {"query": "a"}},
                {"name": "search_jobs", "arguments": {"query": "b"}},
                {"name": "search_jobs", "arguments": {"query": "c"}},
            ],
            "finish_reason": "tool_use",
        }

    llm = FakeLLMClient(responder=responder)
    loop = AgentLoop(
        llm=llm, registry=build_default_registry(), max_turns=1, max_tool_calls_per_turn=2
    )
    ctx = build_context(llm)

    with pytest.raises(TurnBudgetExceededError):
        loop.run(ctx, "search a lot")
