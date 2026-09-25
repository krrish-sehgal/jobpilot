"""Object storage boundary for raw scraped posting payloads.

Every raw posting a scraper fetches is written to object storage
before enrichment touches it, so the original payload is always
recoverable for re-processing (a taxonomy change, an enrichment bug
fix) without re-scraping.
"""

from __future__ import annotations

from typing import Protocol

from jobpilot.config import Settings
from jobpilot.errors import ObjectStorageError


class ObjectStorage(Protocol):
    def put(self, key: str, data: bytes) -> None: ...

    def get(self, key: str) -> bytes: ...

    def exists(self, key: str) -> bool: ...

    def delete(self, key: str) -> None: ...


class HTTPObjectStorage:
    """Real object storage client. Unconfigured until credentials are set."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _require_real_credentials(self) -> None:
        if self._settings.object_storage_access_key.startswith("replace-with"):
            raise ObjectStorageError(
                "no object storage credentials configured "
                "(JOBPILOT_OBJECT_STORAGE_ACCESS_KEY is still a placeholder)"
            )

    def put(self, key: str, data: bytes) -> None:
        self._require_real_credentials()
        raise ObjectStorageError(
            "HTTPObjectStorage is not wired to a live bucket in this environment"
        )

    def get(self, key: str) -> bytes:
        self._require_real_credentials()
        raise ObjectStorageError(
            "HTTPObjectStorage is not wired to a live bucket in this environment"
        )

    def exists(self, key: str) -> bool:
        self._require_real_credentials()
        raise ObjectStorageError(
            "HTTPObjectStorage is not wired to a live bucket in this environment"
        )

    def delete(self, key: str) -> None:
        self._require_real_credentials()
        raise ObjectStorageError(
            "HTTPObjectStorage is not wired to a live bucket in this environment"
        )


class InMemoryObjectStorage:
    """In-memory object storage used by tests and local development."""

    def __init__(self) -> None:
        self._objects: dict[str, bytes] = {}

    def put(self, key: str, data: bytes) -> None:
        self._objects[key] = data

    def get(self, key: str) -> bytes:
        try:
            return self._objects[key]
        except KeyError as exc:
            raise ObjectStorageError(f"no object at key {key!r}") from exc

    def exists(self, key: str) -> bool:
        return key in self._objects

    def delete(self, key: str) -> None:
        self._objects.pop(key, None)
