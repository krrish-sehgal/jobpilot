"""Repository for user facts (long-term memory)."""

from __future__ import annotations

from uuid import UUID

from jobpilot.integrations.supabase_client import Database
from jobpilot.models import UserFact

_TABLE = "user_facts"


class UserFactRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def save(self, fact: UserFact) -> UserFact:
        row = self._db.insert(_TABLE, fact.model_dump(mode="json"))
        return UserFact.model_validate(row)

    def list_for_user(self, user_id: UUID, *, include_superseded: bool = False) -> list[UserFact]:
        rows = self._db.find(_TABLE, user_id=str(user_id))
        facts = [UserFact.model_validate(row) for row in rows]
        if include_superseded:
            return facts
        return [fact for fact in facts if fact.superseded_by is None]

    def supersede(self, old_fact_id: UUID, new_fact_id: UUID) -> None:
        self._db.update(_TABLE, str(old_fact_id), {"superseded_by": str(new_fact_id)})
