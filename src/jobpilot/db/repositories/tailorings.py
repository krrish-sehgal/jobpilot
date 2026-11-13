"""Repository for tailorings and their suggestions.

A tailoring is one header row plus N suggestion rows. The repository
hides that split: callers save and load a single `TailoringRecord`
whose `suggestions` list is populated, in generation order.
"""

from __future__ import annotations

from uuid import UUID

from jobpilot.errors import RecordNotFoundError
from jobpilot.integrations.supabase_client import Database
from jobpilot.resume.models import Decision, Suggestion, TailoringRecord

_TAILORINGS = "tailorings"
_SUGGESTIONS = "tailoring_suggestions"


class TailoringRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def save(self, record: TailoringRecord) -> TailoringRecord:
        """Insert a new tailoring (header and suggestions)."""

        self._db.insert(_TAILORINGS, self._header_row(record))
        self._write_suggestions(record)
        return self.get(record.id)

    def update(self, record: TailoringRecord) -> TailoringRecord:
        """Replace header fields and the whole suggestion list.

        Used when the background run finishes and when decisions change
        the score. Suggestions are rewritten wholesale: the list is
        small (tens of rows) and always produced as a unit.
        """

        self._db.update(_TAILORINGS, str(record.id), self._header_row(record))
        for row in self._db.find(_SUGGESTIONS, tailoring_id=str(record.id)):
            self._db.delete(_SUGGESTIONS, row["id"])
        self._write_suggestions(record)
        return self.get(record.id)

    def get(self, tailoring_id: UUID) -> TailoringRecord:
        header = self._db.get(_TAILORINGS, str(tailoring_id))
        rows = self._db.find(_SUGGESTIONS, tailoring_id=str(tailoring_id))
        rows.sort(key=lambda r: r["position"])
        suggestions = [Suggestion.model_validate(r) for r in rows]
        return TailoringRecord.model_validate({**header, "suggestions": suggestions})

    def get_for_user(self, user_id: UUID, tailoring_id: UUID) -> TailoringRecord:
        record = self.get(tailoring_id)
        if record.user_id != user_id:
            raise RecordNotFoundError(f"no tailoring {tailoring_id}")
        return record

    def set_decisions(self, tailoring_id: UUID, decisions: dict[UUID, Decision]) -> None:
        for suggestion_id, decision in decisions.items():
            self._db.update(_SUGGESTIONS, str(suggestion_id), {"decision": decision.value})

    @staticmethod
    def _header_row(record: TailoringRecord) -> dict:
        row = record.model_dump(mode="json", exclude={"suggestions"})
        return row

    def _write_suggestions(self, record: TailoringRecord) -> None:
        for position, suggestion in enumerate(record.suggestions):
            row = suggestion.model_dump(mode="json")
            row["tailoring_id"] = str(record.id)
            row["position"] = position
            self._db.insert(_SUGGESTIONS, row)
