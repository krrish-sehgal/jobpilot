"""Render a `ScoredJob` as a compact chat-friendly card.

Keeps presentation logic (what to show, how to truncate, how to phrase
a match reason) out of the agent loop and prompts, which should stay
focused on reasoning rather than formatting.
"""

from __future__ import annotations

from jobpilot.models import ScoredJob

_DESCRIPTION_PREVIEW_CHARS = 220


class JobCard(dict):
    """A dict subclass so cards serialize trivially, with typed fields
    documented here for readability."""


def render_job_card(scored: ScoredJob) -> JobCard:
    job = scored.job
    description_preview = job.description[:_DESCRIPTION_PREVIEW_CHARS].rstrip()
    if len(job.description) > _DESCRIPTION_PREVIEW_CHARS:
        description_preview += "…"

    compensation_text = None
    if job.compensation is not None:
        comp = job.compensation
        if comp.min_amount is not None and comp.max_amount is not None:
            compensation_text = (
                f"{comp.currency} {comp.min_amount:,.0f}–{comp.max_amount:,.0f}/{comp.period}"
            )
        elif comp.max_amount is not None:
            compensation_text = f"up to {comp.currency} {comp.max_amount:,.0f}/{comp.period}"
        elif comp.min_amount is not None:
            compensation_text = f"from {comp.currency} {comp.min_amount:,.0f}/{comp.period}"

    return JobCard(
        job_id=str(job.id),
        title=job.title,
        company=job.company,
        location_text=job.location_text,
        seniority_band=job.seniority_band.value,
        role_category=job.role_category.value,
        skills=job.skills[:8],
        description_preview=description_preview,
        compensation_text=compensation_text,
        apply_url=job.apply_url,
        match_score=round(scored.combined_score, 2),
    )


def render_job_cards(scored_jobs: list[ScoredJob]) -> list[JobCard]:
    return [render_job_card(scored) for scored in scored_jobs]
