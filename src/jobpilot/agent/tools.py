"""The five tools the agent can call, plus their JSON-schema definitions.

Each tool has: a Pydantic model for its arguments (used to validate
what the model produced before we ever call real code with it), a
handler function, and a JSON-schema dict in the shape most LLM tool-use
APIs expect. `jobpilot.agent.registry.build_default_registry` wires all
five into a `ToolRegistry`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import UUID

from pydantic import BaseModel, Field

from jobpilot.chat.cards import render_job_card
from jobpilot.db.repositories.jobs import JobRepository
from jobpilot.errors import RecordNotFoundError
from jobpilot.integrations.llm import LLMClient
from jobpilot.memory.store import MemoryStore
from jobpilot.models import JobRecord, LocationTier, SearchFilters, SeniorityBand
from jobpilot.search.hybrid import hybrid_search


class ResumeFetcher(ABC):
    """Base class for fetching a user's resume text.

    A real deployment backs this with object storage or a resume
    parsing service; `StaticResumeFetcher` below is a simple
    dict-backed stand-in used in tests and local development.
    """

    @abstractmethod
    def fetch(self, user_id: UUID) -> str | None: ...


@dataclass
class StaticResumeFetcher(ResumeFetcher):
    resumes_by_user_id: dict[str, str]

    def fetch(self, user_id: UUID) -> str | None:
        return self.resumes_by_user_id.get(str(user_id))


class TailoringLauncher(Protocol):
    """Starts a resume tailoring on the user's behalf.

    Implemented by `jobpilot.resume.service.ResumeService`. Declared here
    as a protocol so the agent layer does not import the resume package.
    Returns a plain dict (`started`, plus either `tailoring_id`/`job_title`
    or a `reason`) because the agent reads the outcome as text.
    """

    def start_from_chat(self, user_id: UUID, job_id: str) -> dict[str, Any]: ...


@dataclass
class TurnArtifacts:
    """Structured by-products of a turn, kept out of the model's context.

    The model only sees each tool's return value as text. UI-ready things
    (full job cards, a started tailoring) are collected here as tools run,
    so the caller can show them without the model having to echo them.
    """

    job_cards: list[dict[str, Any]] = field(default_factory=list)
    tailorings: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class AgentToolContext:
    """Dependencies the tool handlers need, bundled for the agent loop."""

    user_id: UUID
    conversation_id: UUID
    llm: LLMClient
    job_repository: JobRepository
    memory_store: MemoryStore
    resume_fetcher: ResumeFetcher
    candidate_seniority: SeniorityBand | None = None
    preferred_location_tiers: list[LocationTier] | None = None
    saved_job_ids: set[str] = field(default_factory=set)
    tailoring_launcher: TailoringLauncher | None = None
    artifacts: TurnArtifacts = field(default_factory=TurnArtifacts)


# --- search_jobs -----------------------------------------------------


class SearchJobsArgs(BaseModel):
    query: str = Field(
        min_length=1, description="Natural-language description of what the user is looking for."
    )
    limit: int = Field(default=5, ge=1, le=20)


SEARCH_JOBS_SCHEMA = {
    "name": "search_jobs",
    "description": (
        "Search for job postings matching a natural-language description of what "
        "the user wants. Use the user's own words about the kind of role, skills, "
        "or company stage they're after, not a keyword list."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "What the user is looking for, in their words.",
            },
            "limit": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5},
        },
        "required": ["query"],
    },
}


def search_jobs(ctx: AgentToolContext, args: SearchJobsArgs) -> list[dict]:
    all_jobs = ctx.job_repository.list_all()
    results = hybrid_search(
        ctx.llm,
        query_text=args.query,
        candidate_jobs=all_jobs,
        filters=SearchFilters(),
        candidate_seniority=ctx.candidate_seniority,
        limit=args.limit,
    )
    known = {card["job_id"] for card in ctx.artifacts.job_cards}
    for scored in results:
        card = render_job_card(
            scored,
            candidate_seniority=ctx.candidate_seniority,
            preferred_location_tiers=ctx.preferred_location_tiers,
            saved_job_ids=ctx.saved_job_ids,
        )
        if card["job_id"] not in known:
            ctx.artifacts.job_cards.append(dict(card))
            known.add(card["job_id"])
    return [
        {
            "job_id": str(scored.job.id),
            "title": scored.job.title,
            "company": scored.job.company,
            "role_category": scored.job.role_category.value,
            "seniority_band": scored.job.seniority_band.value,
            "location_text": scored.job.location_text,
            "combined_score": round(scored.combined_score, 4),
        }
        for scored in results
    ]


# --- recall_memory -----------------------------------------------------


class RecallMemoryArgs(BaseModel):
    query: str = Field(min_length=1, description="What kind of remembered fact to look for.")
    limit: int = Field(default=5, ge=1, le=10)


RECALL_MEMORY_SCHEMA = {
    "name": "recall_memory",
    "description": (
        "Recall durable facts previously learned about this user (background, "
        "constraints, preferences, goals) relevant to the current query."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 10, "default": 5},
        },
        "required": ["query"],
    },
}


def recall_memory(ctx: AgentToolContext, args: RecallMemoryArgs) -> list[dict]:
    facts = ctx.memory_store.recall(ctx.user_id, args.query, limit=args.limit)
    return [{"fact_text": fact.fact_text, "category": fact.category} for fact in facts]


# --- fetch_resume -----------------------------------------------------


class FetchResumeArgs(BaseModel):
    pass


FETCH_RESUME_SCHEMA = {
    "name": "fetch_resume",
    "description": "Fetch the current user's resume text, if one is on file.",
    "input_schema": {"type": "object", "properties": {}, "required": []},
}


def fetch_resume(ctx: AgentToolContext, args: FetchResumeArgs) -> dict:
    resume_text = ctx.resume_fetcher.fetch(ctx.user_id)
    if resume_text is None:
        return {"found": False, "resume_text": None}
    return {"found": True, "resume_text": resume_text}


# --- get_job_details -----------------------------------------------------


class GetJobDetailsArgs(BaseModel):
    job_id: str = Field(min_length=1, description="The job_id returned by search_jobs.")


GET_JOB_DETAILS_SCHEMA = {
    "name": "get_job_details",
    "description": "Get the full description and details for one specific job by id.",
    "input_schema": {
        "type": "object",
        "properties": {"job_id": {"type": "string"}},
        "required": ["job_id"],
    },
}


def get_job_details(ctx: AgentToolContext, args: GetJobDetailsArgs) -> dict:
    try:
        job: JobRecord = ctx.job_repository.get(UUID(args.job_id))
    except (RecordNotFoundError, ValueError) as exc:
        return {"found": False, "error": str(exc)}

    return {
        "found": True,
        "title": job.title,
        "company": job.company,
        "description": job.description,
        "apply_url": job.apply_url,
        "skills": job.skills,
        "location_text": job.location_text,
        "employment_type": job.employment_type.value,
        "compensation": job.compensation.model_dump() if job.compensation else None,
    }


# --- tailor_resume -----------------------------------------------------


class TailorResumeArgs(BaseModel):
    job_id: str = Field(min_length=1, description="The job_id of the role to tailor for.")


TAILOR_RESUME_SCHEMA = {
    "name": "tailor_resume",
    "description": (
        "Start tailoring the user's primary resume for one specific job. Returns "
        "immediately; suggestions are generated in the background and the user "
        "reviews them in the app. Only call when the user asks to improve or adapt "
        "their resume for a job. Requires a resume on file."
    ),
    "input_schema": {
        "type": "object",
        "properties": {"job_id": {"type": "string"}},
        "required": ["job_id"],
    },
}


def tailor_resume(ctx: AgentToolContext, args: TailorResumeArgs) -> dict:
    if ctx.tailoring_launcher is None:
        return {"started": False, "reason": "unavailable"}
    # The model sometimes repeats a call; one tailoring per job per turn.
    for earlier in ctx.artifacts.tailorings:
        if earlier.get("job_id") == args.job_id:
            return earlier
    result = ctx.tailoring_launcher.start_from_chat(ctx.user_id, args.job_id)
    if result.get("started"):
        ctx.artifacts.tailorings.append(result)
    return result
