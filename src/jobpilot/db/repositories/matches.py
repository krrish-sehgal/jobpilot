"""Repository for persisted match scores between a user and a job.

Backed by the `match_scores` table added in migration 0002. Storing
scored matches (rather than recomputing ranking on every read) lets
the chat layer reference "the match I showed you earlier" and lets
operations query score distributions over time.
"""

from __future__ import annotations

from uuid import UUID

from jobpilot.integrations.supabase_client import Database
from jobpilot.models import ScoredJob

_TABLE = "match_scores"


class MatchScoreRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def save(self, user_id: UUID, scored: ScoredJob) -> dict:
        row = {
            "user_id": str(user_id),
            "job_id": str(scored.job.id),
            "semantic_similarity": scored.semantic_similarity,
            "recency_score": scored.recency_score,
            "seniority_fit_score": scored.seniority_fit_score,
            "location_fit_score": scored.location_fit_score,
            "completeness_score": scored.completeness_score,
            "combined_score": scored.combined_score,
        }
        return self._db.insert(_TABLE, row)

    def list_for_user(self, user_id: UUID) -> list[dict]:
        rows = self._db.find(_TABLE, user_id=str(user_id))
        return sorted(rows, key=lambda r: r["combined_score"], reverse=True)
