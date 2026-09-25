"""Supabase (Postgres) boundary.

Repositories in `jobpilot.db.repositories` code against the `Database`
protocol below rather than against a specific driver, so the fake used
in tests and the real Supabase-backed client are interchangeable.
"""

from __future__ import annotations

import copy
import uuid
from typing import Any, Protocol

from jobpilot.config import Settings
from jobpilot.errors import RecordNotFoundError, RepositoryError


class Database(Protocol):
    """Minimal table-store protocol repositories are built on.

    This deliberately does not expose raw SQL: repositories express
    intent (`insert`, `get`, `find`, `update`, `delete`) and the
    database implementation is responsible for translating that into
    whatever the backend needs.
    """

    def insert(self, table: str, row: dict[str, Any]) -> dict[str, Any]: ...

    def get(self, table: str, row_id: str) -> dict[str, Any]: ...

    def find(self, table: str, **filters: Any) -> list[dict[str, Any]]: ...

    def update(self, table: str, row_id: str, patch: dict[str, Any]) -> dict[str, Any]: ...

    def delete(self, table: str, row_id: str) -> None: ...


class SupabaseDatabase:
    """Real Supabase-backed implementation.

    Unconfigured until `JOBPILOT_SUPABASE_URL` /
    `JOBPILOT_SUPABASE_SERVICE_ROLE_KEY` are set to real values; every
    method fails fast rather than attempting a request against the
    placeholder host.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _require_real_credentials(self) -> None:
        if self._settings.supabase_url.endswith("your-project.supabase.co"):
            raise RepositoryError(
                "no Supabase project configured (JOBPILOT_SUPABASE_URL is still a placeholder)"
            )

    def insert(self, table: str, row: dict[str, Any]) -> dict[str, Any]:
        self._require_real_credentials()
        raise RepositoryError("SupabaseDatabase is not wired to a live project in this environment")

    def get(self, table: str, row_id: str) -> dict[str, Any]:
        self._require_real_credentials()
        raise RepositoryError("SupabaseDatabase is not wired to a live project in this environment")

    def find(self, table: str, **filters: Any) -> list[dict[str, Any]]:
        self._require_real_credentials()
        raise RepositoryError("SupabaseDatabase is not wired to a live project in this environment")

    def update(self, table: str, row_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        self._require_real_credentials()
        raise RepositoryError("SupabaseDatabase is not wired to a live project in this environment")

    def delete(self, table: str, row_id: str) -> None:
        self._require_real_credentials()
        raise RepositoryError("SupabaseDatabase is not wired to a live project in this environment")


class InMemoryDatabase:
    """In-memory table store used by tests and local development.

    Rows are keyed by `id`; if a caller inserts a row without one, an
    id is generated. Returned rows are deep-copied so callers can't
    mutate the store by mutating a returned dict.
    """

    def __init__(self) -> None:
        self._tables: dict[str, dict[str, dict[str, Any]]] = {}

    def _table(self, table: str) -> dict[str, dict[str, Any]]:
        return self._tables.setdefault(table, {})

    def insert(self, table: str, row: dict[str, Any]) -> dict[str, Any]:
        row = dict(row)
        row_id = str(row.get("id") or uuid.uuid4())
        row["id"] = row_id
        self._table(table)[row_id] = copy.deepcopy(row)
        return copy.deepcopy(row)

    def get(self, table: str, row_id: str) -> dict[str, Any]:
        try:
            return copy.deepcopy(self._table(table)[row_id])
        except KeyError as exc:
            raise RecordNotFoundError(f"no row in {table!r} with id {row_id!r}") from exc

    def find(self, table: str, **filters: Any) -> list[dict[str, Any]]:
        results = []
        for row in self._table(table).values():
            if all(row.get(key) == value for key, value in filters.items()):
                results.append(copy.deepcopy(row))
        return results

    def update(self, table: str, row_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        existing = self.get(table, row_id)
        existing.update(patch)
        self._table(table)[row_id] = copy.deepcopy(existing)
        return copy.deepcopy(existing)

    def delete(self, table: str, row_id: str) -> None:
        self._table(table).pop(row_id, None)
