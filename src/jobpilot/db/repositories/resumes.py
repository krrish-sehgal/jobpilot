"""Repository for uploaded resumes."""

from __future__ import annotations

from uuid import UUID

from jobpilot.errors import RecordNotFoundError
from jobpilot.integrations.supabase_client import Database
from jobpilot.resume.models import ResumeRecord

_TABLE = "resumes"


class ResumeRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def save(self, record: ResumeRecord) -> ResumeRecord:
        row = self._db.insert(_TABLE, record.model_dump(mode="json"))
        return ResumeRecord.model_validate(row)

    def update(self, record: ResumeRecord) -> ResumeRecord:
        row = self._db.update(_TABLE, str(record.id), record.model_dump(mode="json"))
        return ResumeRecord.model_validate(row)

    def get_for_user(self, user_id: UUID, resume_id: UUID) -> ResumeRecord:
        """Fetch a resume only if `user_id` owns it.

        A resume that exists but belongs to someone else raises the same
        `RecordNotFoundError` as a missing one, so the API never
        confirms to a caller that another user's resume id is real.
        """

        row = self._db.get(_TABLE, str(resume_id))
        record = ResumeRecord.model_validate(row)
        if record.user_id != user_id:
            raise RecordNotFoundError(f"no resume {resume_id}")
        return record

    def list_for_user(self, user_id: UUID) -> list[ResumeRecord]:
        """Newest upload first."""

        records = [
            ResumeRecord.model_validate(r) for r in self._db.find(_TABLE, user_id=str(user_id))
        ]
        return sorted(records, key=lambda r: r.uploaded_at, reverse=True)

    def primary_for_user(self, user_id: UUID) -> ResumeRecord | None:
        for record in self.list_for_user(user_id):
            if record.is_primary:
                return record
        return None

    def make_primary(self, user_id: UUID, resume_id: UUID) -> None:
        """Make `resume_id` the user's only primary resume.

        Demotes the old primary first, then promotes the new one, so the
        partial unique index (`resumes_one_primary_per_user`) is never
        violated mid-way. A real Postgres implementation would do both
        in one transaction.
        """

        for record in self.list_for_user(user_id):
            if record.is_primary and record.id != resume_id:
                self._db.update(_TABLE, str(record.id), {"is_primary": False})
        self._db.update(_TABLE, str(resume_id), {"is_primary": True})
