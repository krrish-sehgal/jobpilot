"""Repository for jobs a user bookmarked from the website."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import NAMESPACE_URL, UUID, uuid5

from jobpilot.integrations.supabase_client import Database

_TABLE = "saved_jobs"


def _row_id(user_id: UUID, job_id: UUID) -> str:
    """Deterministic row id for a (user, job) pair.

    Deriving the primary key from the pair makes save and unsave
    naturally idempotent against any `Database`: saving twice writes
    the same key, and unsaving a job that was never saved deletes a key
    that does not exist. It mirrors the `unique (user_id, job_id)`
    constraint in the migration.
    """

    return str(uuid5(NAMESPACE_URL, f"jobpilot:saved:{user_id}:{job_id}"))


class SavedJobRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def save(self, user_id: UUID, job_id: UUID) -> None:
        row_id = _row_id(user_id, job_id)
        if self._db.find(_TABLE, id=row_id):
            return
        self._db.insert(
            _TABLE,
            {
                "id": row_id,
                "user_id": str(user_id),
                "job_id": str(job_id),
                "created_at": datetime.now(UTC).isoformat(),
            },
        )

    def remove(self, user_id: UUID, job_id: UUID) -> None:
        self._db.delete(_TABLE, _row_id(user_id, job_id))

    def job_ids_for_user(self, user_id: UUID) -> list[UUID]:
        """Saved job ids, most recently saved first."""

        rows = self._db.find(_TABLE, user_id=str(user_id))
        rows.sort(key=lambda r: r["created_at"], reverse=True)
        return [UUID(r["job_id"]) for r in rows]

    def is_saved(self, user_id: UUID, job_id: UUID) -> bool:
        return bool(self._db.find(_TABLE, id=_row_id(user_id, job_id)))
