"""
Rendering a job match into a "card" — the compact, structured message
format a chat platform would show, as opposed to a wall of text.

This module only shapes data; it does not send anything anywhere.
"""

from __future__ import annotations

from dataclasses import dataclass

from jobpilot.agent.tools import JobResult


@dataclass
class JobCard:
    """A minimal, chat-friendly rendering of a single job match."""

    title_line: str
    detail_line: str
    footer_line: str


def render_job_card(job: JobResult, *, match_reason: str | None = None) -> JobCard:
    """Turn a JobResult into a small card a chat UI could render as a
    button/list item.

    This demo builds the card fields directly from the (fake) job
    fields and does not call any templating or rendering service.
    """
    detail = f"{job.seniority_band.title()} · {job.role_category.replace('_', ' ').title()} · {job.location}"
    footer = match_reason or "Matched on role and location."
    return JobCard(title_line=job.title, detail_line=detail, footer_line=footer)


def render_job_list(jobs: list[JobResult], *, limit: int = 5) -> list[JobCard]:
    """Render several job matches as cards, capped at `limit` so a chat
    reply doesn't turn into a wall of cards."""
    return [render_job_card(job) for job in jobs[:limit]]
