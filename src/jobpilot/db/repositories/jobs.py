"""Repository for `JobRecord` rows."""

from __future__ import annotations

from uuid import UUID

from jobpilot.errors import RecordNotFoundError
from jobpilot.integrations.supabase_client import Database
from jobpilot.models import JobRecord

_TABLE = "jobs"


class JobRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def save(self, job: JobRecord) -> JobRecord:
        row = self._db.insert(_TABLE, _to_row(job))
        return _from_row(row)

    def get(self, job_id: UUID) -> JobRecord:
        row = self._db.get(_TABLE, str(job_id))
        return _from_row(row)

    def find_by_content_hash(self, content_hash: str) -> JobRecord | None:
        rows = self._db.find(_TABLE, content_hash=content_hash)
        if not rows:
            return None
        return _from_row(rows[0])

    def find_by_role_category(self, role_category: str) -> list[JobRecord]:
        rows = self._db.find(_TABLE, role_category=role_category)
        return [_from_row(row) for row in rows]

    def list_all(self) -> list[JobRecord]:
        # InMemoryDatabase.find with no filters returns everything;
        # a real Postgres-backed implementation would paginate this.
        rows = self._db.find(_TABLE)
        return [_from_row(row) for row in rows]

    def delete(self, job_id: UUID) -> None:
        try:
            self.get(job_id)
        except RecordNotFoundError:
            return
        self._db.delete(_TABLE, str(job_id))


def _to_row(job: JobRecord) -> dict:
    row = job.model_dump(mode="json")
    return row


def _from_row(row: dict) -> JobRecord:
    return JobRecord.model_validate(row)
