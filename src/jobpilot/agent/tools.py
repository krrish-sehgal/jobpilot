"""
Tool definitions available to the agent loop.

Each tool is a plain function with a typed signature and a docstring
that doubles as the description the model would see. A real system
would register these with an LLM client's tool-calling API; here they
just exist to show the *shape* of a tool: inputs, outputs, and what
each one is responsible for.

Nothing here performs real work. See loop.py for how these would be
selected and called in sequence.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class JobResult:
    """One row of a search_jobs result."""

    job_id: str
    title: str
    role_category: str
    seniority_band: str
    location: str
    summary: str


@dataclass
class MemoryFact:
    """One durable fact recalled about a user."""

    fact_id: str
    text: str
    confidence: float


@dataclass
class ResumeSnapshot:
    """A very small stand-in for a parsed resume."""

    user_id: str
    headline: str
    years_experience: float
    skills: list[str] = field(default_factory=list)


def search_jobs(
    query: str,
    *,
    city: str | None = None,
    min_years: float | None = None,
    role_category: str | None = None,
    limit: int = 10,
) -> list[JobResult]:
    """Search the job index for postings matching a free-text query plus
    optional structured filters.

    In a real implementation this would call the hybrid search step
    (see search/hybrid.py), combining semantic similarity with the
    filters given here. In this demo it returns a couple of obviously
    fake rows so the agent loop has something to "reason" over.
    """
    return [
        JobResult(
            job_id="demo-job-1",
            title="Junior Data Analyst",
            role_category="data_and_analytics",
            seniority_band="entry",
            location=city or "Remote",
            summary="Fake demo posting returned by a stub, not a real listing.",
        ),
        JobResult(
            job_id="demo-job-2",
            title="Support Engineer",
            role_category="engineering",
            seniority_band="junior",
            location=city or "Remote",
            summary="Fake demo posting returned by a stub, not a real listing.",
        ),
    ][:limit]


def recall_memory(user_id: str, *, about: str | None = None, limit: int = 5) -> list[MemoryFact]:
    """Retrieve durable facts previously extracted about a user.

    Real memory would be retrieved by meaning (an embedding lookup)
    against facts written by a background extraction step. This stub
    just returns a couple of invented example facts.
    """
    return [
        MemoryFact(fact_id="fact-1", text="Prefers remote or hybrid roles.", confidence=0.8),
        MemoryFact(fact_id="fact-2", text="Has about two years of experience.", confidence=0.6),
    ][:limit]


def fetch_resume(user_id: str) -> ResumeSnapshot:
    """Fetch the most recent parsed resume snapshot for a user.

    A real version would pull structured fields out of an uploaded
    resume file. This demo always returns the same placeholder snapshot.
    """
    return ResumeSnapshot(
        user_id=user_id,
        headline="Demo Candidate — placeholder resume",
        years_experience=2.0,
        skills=["python", "sql"],
    )


# A registry mapping a tool name (as the model would refer to it) to the
# callable. The agent loop looks names up here rather than importing each
# tool function directly, which keeps the loop code decoupled from the
# individual tool implementations.
TOOL_REGISTRY = {
    "search_jobs": search_jobs,
    "recall_memory": recall_memory,
    "fetch_resume": fetch_resume,
}
