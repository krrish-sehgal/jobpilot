"""The ranking engine: combines weighted signals into one score.

Five signals, each normalized to [0, 1], combined by a weighted sum.
Weights come from `Settings` (or an explicit override) and must sum to
1.0 within a small floating-point tolerance — `RankingWeightError` is
raised otherwise, since a silently-unnormalized weight set would make
`combined_score` not comparable across queries.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from jobpilot.errors import RankingWeightError
from jobpilot.models import (
    SENIORITY_ORDER,
    JobRecord,
    LocationTier,
    ScoredJob,
    SeniorityBand,
)

_WEIGHT_SUM_TOLERANCE = 1e-6


@dataclass(frozen=True)
class RankingWeights:
    semantic: float = 0.45
    recency: float = 0.15
    seniority_fit: float = 0.20
    location_fit: float = 0.10
    completeness: float = 0.10

    def __post_init__(self) -> None:
        total = (
            self.semantic
            + self.recency
            + self.seniority_fit
            + self.location_fit
            + self.completeness
        )
        if abs(total - 1.0) > _WEIGHT_SUM_TOLERANCE:
            raise RankingWeightError(f"ranking weights must sum to 1.0, got {total}")


def recency_score(
    posted_at: datetime | None, *, now: datetime | None = None, half_life_days: float = 14.0
) -> float:
    """Exponential decay score: 1.0 for a posting made right now, 0.5
    after `half_life_days`, approaching 0 as the posting ages further.

    A posting with no `posted_at` (a platform that doesn't expose one)
    scores a neutral 0.5 rather than 0, since missing data shouldn't
    be penalized as harshly as "definitely stale".
    """

    if posted_at is None:
        return 0.5
    now = now or datetime.now(UTC)
    if posted_at.tzinfo is None:
        posted_at = posted_at.replace(tzinfo=UTC)
    age_days = max(0.0, (now - posted_at).total_seconds() / 86400)
    return 0.5 ** (age_days / half_life_days)


def seniority_fit_score(job_band: SeniorityBand, candidate_band: SeniorityBand | None) -> float:
    """1.0 for an exact band match, decaying with ordinal distance.

    A candidate with no known seniority (`candidate_band is None`)
    scores a neutral 0.5 — we don't want to penalize a query where the
    user hasn't stated a level, but we also shouldn't claim a perfect
    fit we can't support.
    """

    if candidate_band is None:
        return 0.5
    distance = abs(SENIORITY_ORDER[job_band] - SENIORITY_ORDER[candidate_band])
    # Distances range 0..4; map linearly to 1.0..0.0.
    return max(0.0, 1.0 - distance / 4.0)


def location_fit_score(job_tier: LocationTier, preferred_tiers: list[LocationTier] | None) -> float:
    """1.0 if the job's tier is in the candidate's preferred tiers.

    An empty/`None` preference list means "no preference" and scores a
    neutral 0.5 for every tier. `LocationTier.UNKNOWN` on the job side
    always scores 0.3: we can't confirm a fit, but we don't want to
    zero out a posting purely because a scraper couldn't parse its
    location text.
    """

    if job_tier == LocationTier.UNKNOWN:
        return 0.3
    if not preferred_tiers:
        return 0.5
    return 1.0 if job_tier in preferred_tiers else 0.0


def completeness_score(job: JobRecord) -> float:
    """Fraction of "nice to have" fields present, as a data-quality proxy.

    A posting missing compensation, skills, and location is more
    likely to be low-effort or stale than one with all fields filled
    in, so this nudges thin postings down without excluding them.
    """

    checks = [
        bool(job.skills),
        job.compensation is not None,
        job.location_tier != LocationTier.UNKNOWN,
        job.posted_at is not None,
        len(job.description) >= 200,
    ]
    return sum(checks) / len(checks)


def score_job(
    job: JobRecord,
    *,
    semantic_similarity: float,
    candidate_seniority: SeniorityBand | None = None,
    preferred_location_tiers: list[LocationTier] | None = None,
    weights: RankingWeights | None = None,
    now: datetime | None = None,
) -> ScoredJob:
    """Combine all five signals into a `ScoredJob`."""

    if not 0.0 <= semantic_similarity <= 1.0:
        raise ValueError("semantic_similarity must be in [0, 1]")

    weights = weights or RankingWeights()
    recency = recency_score(job.posted_at, now=now)
    seniority = seniority_fit_score(job.seniority_band, candidate_seniority)
    location = location_fit_score(job.location_tier, preferred_location_tiers)
    completeness = completeness_score(job)

    combined = (
        weights.semantic * semantic_similarity
        + weights.recency * recency
        + weights.seniority_fit * seniority
        + weights.location_fit * location
        + weights.completeness * completeness
    )
    combined = max(0.0, min(1.0, combined))

    return ScoredJob(
        job=job,
        semantic_similarity=semantic_similarity,
        recency_score=recency,
        seniority_fit_score=seniority,
        location_fit_score=location,
        completeness_score=completeness,
        combined_score=combined,
    )


def rank_jobs(scored_jobs: list[ScoredJob], *, limit: int | None = None) -> list[ScoredJob]:
    """Sort by `combined_score` descending, breaking ties by recency."""

    ranked = sorted(scored_jobs, key=lambda sj: (sj.combined_score, sj.recency_score), reverse=True)
    return ranked[:limit] if limit is not None else ranked
