"""Hybrid retrieval: structured filters narrow the candidate set, then
semantic similarity and the ranking engine order it.

Filtering before embedding comparison matters for correctness, not
just speed: a semantically perfect match in the wrong location tier or
outside the requested seniority band is still a wrong answer, and hard
filters are the only way to guarantee it never surfaces.
"""

from __future__ import annotations

from jobpilot.integrations.llm import LLMClient
from jobpilot.models import JobRecord, ScoredJob, SearchFilters, SeniorityBand
from jobpilot.search.embed import cosine_similarity, embed_candidate_profile, embed_query
from jobpilot.search.ranking import RankingWeights, score_job


def apply_filters(jobs: list[JobRecord], filters: SearchFilters) -> list[JobRecord]:
    """Return the subset of `jobs` passing every hard filter in `filters`."""

    result = []
    for job in jobs:
        if filters.role_categories and job.role_category not in filters.role_categories:
            continue
        if filters.seniority_bands and job.seniority_band not in filters.seniority_bands:
            continue
        if filters.location_tiers and job.location_tier not in filters.location_tiers:
            continue
        if filters.employment_types and job.employment_type not in filters.employment_types:
            continue
        if filters.exclude_fraud_signals and job.fraud_signal in filters.exclude_fraud_signals:
            continue
        if (
            filters.max_years_experience is not None
            and job.min_years_experience > filters.max_years_experience
        ):
            continue
        if filters.min_compensation is not None:
            if job.compensation is None or job.compensation.max_amount is None:
                continue
            if job.compensation.max_amount < filters.min_compensation:
                continue
        result.append(job)
    return result


def hybrid_search(
    llm: LLMClient,
    *,
    query_text: str,
    candidate_jobs: list[JobRecord],
    filters: SearchFilters | None = None,
    candidate_seniority: SeniorityBand | None = None,
    weights: RankingWeights | None = None,
    limit: int = 20,
    job_embeddings: dict[str, list[float]] | None = None,
) -> list[ScoredJob]:
    """Filter, embed, score, and rank `candidate_jobs` against `query_text`.

    `job_embeddings`, keyed by `JobRecord.id` (as a string), lets a
    caller pass precomputed embeddings (as a real deployment would,
    reading them from `jobs.candidate_profile_embedding`) instead of
    re-embedding every candidate on every search call.
    """

    filters = filters or SearchFilters()
    filtered = apply_filters(candidate_jobs, filters)
    if not filtered:
        return []

    query_vector = embed_query(llm, query_text)

    preferred_tiers = filters.location_tiers or None

    scored: list[ScoredJob] = []
    for job in filtered:
        job_id = str(job.id)
        if job_embeddings is not None and job_id in job_embeddings:
            job_vector = job_embeddings[job_id]
        else:
            job_vector = embed_candidate_profile(llm, job)
        similarity = cosine_similarity(query_vector, job_vector)
        scored.append(
            score_job(
                job,
                semantic_similarity=similarity,
                candidate_seniority=candidate_seniority,
                preferred_location_tiers=preferred_tiers,
                weights=weights,
            )
        )

    scored.sort(key=lambda sj: (sj.combined_score, sj.recency_score), reverse=True)
    return scored[:limit]
