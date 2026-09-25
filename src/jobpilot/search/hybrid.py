"""
Hybrid search: combining semantic similarity with structured hard
filters.

Neither half works well alone. Pure semantic search can surface a
posting that reads similarly but is three years too senior, or on the
wrong continent. Pure filtering can hand back fifty postings that all
technically match "years >= 2, city = X" but have nothing to do with
what the person is actually looking for. This module represents the
step that combines both signals before ranking.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SearchFilters:
    """The structured, hard-constraint side of a search."""

    city: str | None = None
    min_years: float | None = None
    role_category: str | None = None


@dataclass
class CandidateMatch:
    """One job considered as a match, carrying both signals that will
    feed into ranking.py."""

    job_id: str
    semantic_score: float
    passes_filters: bool


def apply_filters(job_ids: list[str], filters: SearchFilters) -> list[str]:
    """Narrow a list of job ids down to those that satisfy the
    structured filters (years of experience, city, role category).

    A real implementation would run this as a WHERE clause against the
    `jobs` table (see db/schema.sql). This stub does no filtering.
    """
    raise NotImplementedError("demo only: no real database is connected")


def semantic_candidates(query_vector: list[float], *, limit: int = 50) -> list[CandidateMatch]:
    """Return the top semantic matches for a query vector against the
    ideal-candidate-description index (see docs/architecture.md for
    why it's an ideal-candidate description and not the job text).

    A real implementation would run an approximate nearest-neighbour
    search against a vector index. This stub returns nothing.
    """
    raise NotImplementedError("demo only: no real vector index is connected")


def hybrid_search(query_vector: list[float], filters: SearchFilters, *, limit: int = 20) -> list[CandidateMatch]:
    """Combine semantic_candidates and apply_filters into one candidate
    list for ranking.rank_candidates to order.

    Intended shape:

        candidates = semantic_candidates(query_vector, limit=limit * 5)
        allowed_ids = set(apply_filters([c.job_id for c in candidates], filters))
        return [c for c in candidates if c.job_id in allowed_ids][:limit]

    Not executed here since both halves it depends on are stubs.
    """
    raise NotImplementedError("demo only: see docstring for the intended control flow")
