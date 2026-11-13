"""Object storage boundary for raw scraped posting payloads.

Every raw posting a scraper fetches is written to object storage
before enrichment touches it, so the original payload is always
recoverable for re-processing (a taxonomy change, an enrichment bug
fix) without re-scraping.
"""

from __future__ import annotations

from typing import Any, Protocol

from botocore.exceptions import BotoCoreError, ClientError

from jobpilot.config import Settings
from jobpilot.errors import ObjectStorageError


class ObjectStorage(Protocol):
    def put(self, key: str, data: bytes) -> None: ...

    def get(self, key: str) -> bytes: ...

    def exists(self, key: str) -> bool: ...

    def delete(self, key: str) -> None: ...


class S3ObjectStorage:
    """S3-compatible object storage (AWS S3, R2, MinIO, Supabase Storage).

    Uses `Settings.object_storage_endpoint` / `_bucket` / `_access_key` /
    `_secret_key`. `boto3` is imported on construction, and a
    preconfigured client can be passed in instead.
    """

    def __init__(self, settings: Settings, *, client: Any | None = None) -> None:
        self._bucket = settings.object_storage_bucket
        if client is None:
            if settings.object_storage_access_key.startswith("replace-with"):
                raise ObjectStorageError(
                    "no object storage credentials configured "
                    "(JOBPILOT_OBJECT_STORAGE_ACCESS_KEY is still a placeholder)"
                )
            import boto3

            client = boto3.client(
                "s3",
                endpoint_url=settings.object_storage_endpoint,
                aws_access_key_id=settings.object_storage_access_key,
                aws_secret_access_key=settings.object_storage_secret_key,
            )
        self._client = client

    def put(self, key: str, data: bytes) -> None:
        try:
            self._client.put_object(Bucket=self._bucket, Key=key, Body=data)
        except (BotoCoreError, ClientError) as exc:
            raise ObjectStorageError(f"could not write object {key!r}: {exc}") from exc

    def get(self, key: str) -> bytes:
        try:
            return self._client.get_object(Bucket=self._bucket, Key=key)["Body"].read()
        except ClientError as exc:
            if _error_code(exc) in _MISSING_CODES:
                raise ObjectStorageError(f"no object at key {key!r}") from exc
            raise ObjectStorageError(f"could not read object {key!r}: {exc}") from exc
        except BotoCoreError as exc:
            raise ObjectStorageError(f"could not read object {key!r}: {exc}") from exc

    def exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
        except ClientError as exc:
            if _error_code(exc) in _MISSING_CODES:
                return False
            raise ObjectStorageError(f"could not check object {key!r}: {exc}") from exc
        except BotoCoreError as exc:
            raise ObjectStorageError(f"could not check object {key!r}: {exc}") from exc
        return True

    def delete(self, key: str) -> None:
        try:
            self._client.delete_object(Bucket=self._bucket, Key=key)
        except (BotoCoreError, ClientError) as exc:
            raise ObjectStorageError(f"could not delete object {key!r}: {exc}") from exc


_MISSING_CODES = {"404", "NoSuchKey", "NotFound"}


def _error_code(exc: ClientError) -> str:
    return str(exc.response.get("Error", {}).get("Code", ""))


class InMemoryObjectStorage:
    """In-memory object storage: the test double, also used for local development."""

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
