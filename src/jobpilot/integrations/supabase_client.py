"""Supabase (Postgres) boundary.

Repositories in `jobpilot.db.repositories` code against the `Database`
protocol below rather than against a specific driver, so the fake used
in tests and the Supabase-backed client are interchangeable.
"""

from __future__ import annotations

import copy
import time
import uuid
from collections.abc import Callable
from typing import Any, Protocol

import httpx

from jobpilot.config import Settings
from jobpilot.errors import RecordNotFoundError, RepositoryError
from jobpilot.utils.retry import RetryExhaustedError, retry_call


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
    """`Database` over Supabase's PostgREST API (`/rest/v1/<table>`).

    Authenticates with the service-role key, so it must only run in
    trusted server-side code. Transient failures (429, 5xx, transport
    errors) are retried with jittered backoff; everything else surfaces
    as `RepositoryError` (`RecordNotFoundError` for a missing row).
    """

    _PAGE_SIZE = 1000

    def __init__(
        self,
        settings: Settings,
        *,
        http_client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._settings = settings
        self._base_url = settings.supabase_url.rstrip("/") + "/rest/v1"
        self._http = http_client or httpx.Client(timeout=30.0)
        self._sleep = sleep

    def insert(self, table: str, row: dict[str, Any]) -> dict[str, Any]:
        """Insert `row`, or replace the row with the same `id` (upsert)."""

        row = dict(row)
        row.setdefault("id", str(uuid.uuid4()))
        rows = self._request(
            "POST",
            table,
            params={"on_conflict": "id"},
            json=row,
            prefer="resolution=merge-duplicates,return=representation",
        )
        return self._one(table, rows, row["id"])

    def get(self, table: str, row_id: str) -> dict[str, Any]:
        rows = self._request("GET", table, params={"id": f"eq.{row_id}", "limit": "1"})
        return self._one(table, rows, row_id)

    def find(self, table: str, **filters: Any) -> list[dict[str, Any]]:
        params = {key: _eq_filter(value) for key, value in filters.items()}
        results: list[dict[str, Any]] = []
        offset = 0
        while True:
            page = self._request(
                "GET",
                table,
                params={
                    **params,
                    "order": "id.asc",
                    "limit": str(self._PAGE_SIZE),
                    "offset": str(offset),
                },
            )
            results.extend(page)
            if len(page) < self._PAGE_SIZE:
                return results
            offset += self._PAGE_SIZE

    def update(self, table: str, row_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        rows = self._request(
            "PATCH",
            table,
            params={"id": f"eq.{row_id}"},
            json=patch,
            prefer="return=representation",
        )
        return self._one(table, rows, row_id)

    def delete(self, table: str, row_id: str) -> None:
        self._request("DELETE", table, params={"id": f"eq.{row_id}"})

    @staticmethod
    def _one(table: str, rows: list[dict[str, Any]], row_id: str) -> dict[str, Any]:
        if not rows:
            raise RecordNotFoundError(f"no row in {table!r} with id {row_id!r}")
        return rows[0]

    def _request(
        self,
        method: str,
        table: str,
        *,
        params: dict[str, str],
        json: dict[str, Any] | None = None,
        prefer: str | None = None,
    ) -> list[dict[str, Any]]:
        if self._settings.supabase_url.endswith("your-project.supabase.co"):
            raise RepositoryError(
                "no Supabase project configured (JOBPILOT_SUPABASE_URL is still a placeholder)"
            )
        key = self._settings.supabase_service_role_key
        headers = {"apikey": key, "Authorization": f"Bearer {key}"}
        if prefer:
            headers["Prefer"] = prefer

        def attempt() -> httpx.Response:
            try:
                response = self._http.request(
                    method,
                    f"{self._base_url}/{table}",
                    params=params,
                    json=json,
                    headers=headers,
                )
            except httpx.TransportError as exc:
                raise _RetryableError(f"transport error: {exc}") from exc
            if response.status_code == 429 or response.status_code >= 500:
                raise _RetryableError(f"PostgREST returned HTTP {response.status_code}")
            return response

        try:
            response = retry_call(
                attempt,
                max_attempts=self._settings.retry_max_attempts,
                base_delay_seconds=self._settings.retry_base_delay_seconds,
                max_delay_seconds=self._settings.retry_max_delay_seconds,
                retry_on=(_RetryableError,),
                sleep=self._sleep,
            )
        except RetryExhaustedError as exc:
            raise RepositoryError(f"{method} {table} failed: {exc.last_exception}") from exc
        if response.status_code >= 400:
            raise RepositoryError(
                f"{method} {table} failed with HTTP {response.status_code}: {response.text[:200]}"
            )
        if not response.content:
            return []
        body = response.json()
        return body if isinstance(body, list) else [body]


class _RetryableError(Exception):
    """Internal: a failure worth retrying."""


def _eq_filter(value: Any) -> str:
    """PostgREST filter expression for equality with `value`."""

    if value is None:
        return "is.null"
    if isinstance(value, bool):
        return f"eq.{str(value).lower()}"
    return f"eq.{value}"


class InMemoryDatabase:
    """In-memory table store: the test double, also used for local development.

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
