"""Event hook on the agent loop, the tailor_resume tool, and richer job cards."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from jobpilot.agent.events import AgentEvent, summarize_tool_result
from jobpilot.agent.loop import AgentLoop
from jobpilot.agent.registry import build_default_registry
from jobpilot.chat.cards import match_reasons, render_job_card
from jobpilot.integrations.llm import FakeLLMClient
from jobpilot.models import CompensationRange, LocationTier, SeniorityBand
from jobpilot.search.ranking import score_job
from tests.conftest import make_job_record
from tests.test_agent_loop import build_context


def scripted(*steps):
    """A responder that returns each scripted step in order."""

    queue = list(steps)
    return lambda system_prompt, messages: queue.pop(0)


def tool_step(name, arguments):
    return {
        "content": None,
        "tool_calls": [{"name": name, "arguments": arguments}],
        "finish_reason": "tool_use",
    }


FINAL = {"content": "Here you go.", "tool_calls": [], "finish_reason": "stop"}


def run_with_events(llm, message="find jobs"):
    events: list[AgentEvent] = []
    ctx = build_context(llm)
    loop = AgentLoop(llm=llm, registry=build_default_registry(), max_turns=4)
    turn = loop.run(ctx, message, on_event=events.append)
    return turn, events, ctx


def test_events_follow_the_loop_in_order():
    llm = FakeLLMClient(
        responder=scripted(tool_step("search_jobs", {"query": "remote backend roles"}), FINAL)
    )
    turn, events, ctx = run_with_events(llm)
    assert [e.kind for e in events] == [
        "status",  # thinking
        "status",  # calling_tool
        "tool_call",
        "tool_result",
        "status",  # thinking (second model round trip)
        "status",  # writing
    ]
    assert [e.data.get("phase") for e in events if e.kind == "status"] == [
        "thinking",
        "calling_tool",
        "thinking",
        "writing",
    ]
    call, result = events[2], events[3]
    assert call.data["label"] == "Searching remote backend roles"
    assert call.data["call_id"] == result.data["call_id"] == str(turn.tool_calls[0].id)
    assert result.data["ok"] is True and result.data["summary"] == "Found 1 matching role"
    assert isinstance(result.result, list)  # raw result travels on the event


def test_failed_tool_call_reports_ok_false():
    llm = FakeLLMClient(responder=scripted(tool_step("search_jobs", {"query": ""}), FINAL))
    _, events, _ = run_with_events(llm)
    result = next(e for e in events if e.kind == "tool_result")
    assert result.data["ok"] is False


def test_a_broken_hook_never_fails_the_turn():
    llm = FakeLLMClient(responder=scripted(FINAL))
    ctx = build_context(llm)
    loop = AgentLoop(llm=llm, registry=build_default_registry())

    def explode(event):
        raise RuntimeError("client went away")

    assert loop.run(ctx, "hi", on_event=explode).final_reply == "Here you go."


def test_summaries_for_each_tool():
    assert summarize_tool_result("search_jobs", []) == "No matching roles found"
    assert summarize_tool_result("fetch_resume", {"found": False}) == "No resume on file"
    assert (
        summarize_tool_result("tailor_resume", {"started": False, "reason": "no_resume"})
        == "You have not uploaded a resume yet"
    )


# --- tailor_resume --------------------------------------------------------


class FakeLauncher:
    def __init__(self, result):
        self.result = result
        self.calls: list[tuple[UUID, str]] = []

    def start_from_chat(self, user_id, job_id):
        self.calls.append((user_id, job_id))
        return self.result


def test_tailor_resume_tool_records_the_started_tailoring_once():
    started = {"started": True, "tailoring_id": str(uuid4()), "job_id": "job-1", "job_title": "SWE"}
    launcher = FakeLauncher(started)
    llm = FakeLLMClient(
        responder=scripted(
            tool_step("tailor_resume", {"job_id": "job-1"}),
            tool_step("tailor_resume", {"job_id": "job-1"}),
            FINAL,
        )
    )
    ctx = build_context(llm)
    ctx.tailoring_launcher = launcher
    loop = AgentLoop(llm=llm, registry=build_default_registry(), max_turns=4)
    loop.run(ctx, "tailor my resume")
    assert len(launcher.calls) == 1  # the repeat call did not start a second job
    assert ctx.artifacts.tailorings == [started]


def test_tailor_resume_without_a_launcher_or_resume_does_not_start():
    llm = FakeLLMClient(responder=scripted(tool_step("tailor_resume", {"job_id": "j"}), FINAL))
    ctx = build_context(llm)
    loop = AgentLoop(llm=llm, registry=build_default_registry())
    turn = loop.run(ctx, "tailor")
    assert turn.tool_calls[0].result == {"started": False, "reason": "unavailable"}
    assert ctx.artifacts.tailorings == []


# --- job cards --------------------------------------------------------------


def test_search_collects_full_cards_without_bloating_the_tool_result():
    llm = FakeLLMClient(responder=scripted(tool_step("search_jobs", {"query": "backend"}), FINAL))
    ctx = build_context(llm)
    ctx.saved_job_ids = {str(j.id) for j in ctx.job_repository.list_all()}
    AgentLoop(llm=llm, registry=build_default_registry()).run(ctx, "jobs")
    card = ctx.artifacts.job_cards[0]
    assert {"match_reasons", "location_tier", "posted_at", "is_saved"} <= card.keys()
    assert card["is_saved"] is True and card["location_tier"] == "remote"


def _scored(**kwargs):
    job = make_job_record(**kwargs.pop("job", {}))
    defaults = {"semantic_similarity": 0.8}
    return score_job(job, **{**defaults, **kwargs})


def test_match_reasons_come_from_the_ranking_signals():
    scored = _scored(
        candidate_seniority=SeniorityBand.SENIOR,
        preferred_location_tiers=[LocationTier.REMOTE],
        job={"compensation": CompensationRange(currency="USD", min_amount=1, max_amount=2)},
    )
    reasons = match_reasons(
        scored,
        candidate_seniority=SeniorityBand.SENIOR,
        preferred_location_tiers=[LocationTier.REMOTE],
        max_reasons=10,
    )
    assert reasons == [
        "Strong skills overlap",
        "Remote, matches your preference",
        "Matches your senior level",
        "Posted recently",
        "Compensation listed",
    ]


def test_match_reasons_stay_silent_on_neutral_signals():
    scored = _scored(semantic_similarity=0.3, job={"location_tier": LocationTier.ONSITE})
    reasons = match_reasons(scored, preferred_location_tiers=[LocationTier.REMOTE])
    assert "Remote, matches your preference" not in reasons
    assert reasons == ["Posted recently"]
    stale = _scored(semantic_similarity=0.3, job={"posted_at": datetime(2020, 1, 1, tzinfo=UTC)})
    assert match_reasons(stale) == ["Relevant to your search"]


def test_card_has_contract_fields():
    card = render_job_card(_scored())
    assert card["posted_at"] is not None and card["is_saved"] is False
    assert card["location_tier"] == "remote"
