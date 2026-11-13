"""Render a `ScoredJob` as a compact chat-friendly card.

Keeps presentation logic (what to show, how to truncate, how to phrase
a match reason) out of the agent loop and prompts, which should stay
focused on reasoning rather than formatting.
"""

from __future__ import annotations

from collections.abc import Collection

from jobpilot.models import LocationTier, ScoredJob, SeniorityBand

_DESCRIPTION_PREVIEW_CHARS = 220


_TIER_LABELS = {
    LocationTier.REMOTE: "Remote",
    LocationTier.HYBRID: "Hybrid",
    LocationTier.ONSITE: "On-site",
}


class JobCard(dict):
    """A dict subclass so cards serialize trivially, with typed fields
    documented here for readability."""


def match_reasons(
    scored: ScoredJob,
    *,
    candidate_seniority: SeniorityBand | None = None,
    preferred_location_tiers: list[LocationTier] | None = None,
    max_reasons: int = 3,
) -> list[str]:
    """Plain-language reasons a job ranked well, derived from its signals.

    These are read straight off the ranking signals already computed for
    the job (`ScoredJob`), never invented by the model, so a reason is
    only shown when the number behind it supports it. A signal that is
    only neutral (no stated preference, unknown level) produces nothing.
    """

    job = scored.job
    reasons: list[str] = []
    if scored.semantic_similarity >= 0.75:
        reasons.append("Strong skills overlap")
    elif scored.semantic_similarity >= 0.6:
        reasons.append("Good skills overlap")
    if scored.location_fit_score == 1.0 and preferred_location_tiers:
        label = _TIER_LABELS.get(job.location_tier)
        if label:
            reasons.append(f"{label}, matches your preference")
    if candidate_seniority is not None and scored.seniority_fit_score == 1.0:
        reasons.append(f"Matches your {job.seniority_band.value} level")
    if scored.recency_score >= 0.8:
        reasons.append("Posted recently")
    if job.compensation is not None:
        reasons.append("Compensation listed")
    return (reasons or ["Relevant to your search"])[:max_reasons]


def render_job_card(
    scored: ScoredJob,
    *,
    candidate_seniority: SeniorityBand | None = None,
    preferred_location_tiers: list[LocationTier] | None = None,
    saved_job_ids: Collection[str] = (),
) -> JobCard:
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
        location_tier=job.location_tier.value,
        match_reasons=match_reasons(
            scored,
            candidate_seniority=candidate_seniority,
            preferred_location_tiers=preferred_location_tiers,
        ),
        posted_at=job.posted_at.isoformat() if job.posted_at else None,
        is_saved=str(job.id) in saved_job_ids,
    )


def render_job_cards(scored_jobs: list[ScoredJob], **kwargs) -> list[JobCard]:
    return [render_job_card(scored, **kwargs) for scored in scored_jobs]
