"""
Final ranking step: orders the candidates hybrid_search produced.

Kept as a separate step from hybrid_search on purpose — combining
signals into a candidate set and deciding the final order are
different concerns, and a real system would likely want to tune or
A/B test the ranking formula without touching how candidates are
gathered.
"""

from __future__ import annotations

from dataclasses import dataclass

from jobpilot.search.hybrid import CandidateMatch


@dataclass
class RankedJob:
    """A candidate with its final rank score attached."""

    job_id: str
    score: float


def rank_candidates(candidates: list[CandidateMatch], *, recency_boost: float = 0.0) -> list[RankedJob]:
    """Order a list of candidates that already passed structured
    filters, using their semantic score plus an optional recency
    signal.

    A real ranking step might blend in several more signals (recency,
    how often a posting gets applied to, how complete its record is).
    This demo does no real scoring — it exists to show where in the
    pipeline final ordering happens, distinct from hybrid_search's job
    of gathering candidates.
    """
    raise NotImplementedError("demo only: no real ranking model is connected")
