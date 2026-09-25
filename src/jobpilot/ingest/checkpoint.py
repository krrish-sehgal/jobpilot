"""Checkpoint bookkeeping so a scraper restart resumes instead of
re-scraping a platform from the beginning.

A checkpoint is per-platform state: the pagination cursor to resume
from and a handful of counters for observability. `CheckpointStore`
wraps the `ingest_checkpoints` table (via `Database`) behind a small
interface the scraper runner uses at the start and end of every run.
"""

from __future__ import annotations

from datetime import datetime

from jobpilot.errors import CheckpointError, RecordNotFoundError
from jobpilot.integrations.supabase_client import Database
from jobpilot.models import IngestCheckpoint

_TABLE = "ingest_checkpoints"


class CheckpointStore:
    def __init__(self, db: Database) -> None:
        self._db = db

    def load(self, source_platform: str) -> IngestCheckpoint:
        """Return the checkpoint for `source_platform`, or a fresh one
        (cursor=None) if none has been saved yet."""

        try:
            row = self._db.get(_TABLE, source_platform)
        except RecordNotFoundError:
            return IngestCheckpoint(source_platform=source_platform)
        return IngestCheckpoint.model_validate(row)

    def save(self, checkpoint: IngestCheckpoint) -> IngestCheckpoint:
        row = checkpoint.model_dump(mode="json")
        row["id"] = checkpoint.source_platform
        try:
            self._db.get(_TABLE, checkpoint.source_platform)
            updated = self._db.update(_TABLE, checkpoint.source_platform, row)
        except RecordNotFoundError:
            updated = self._db.insert(_TABLE, row)
        return IngestCheckpoint.model_validate(updated)

    def start_run(self, source_platform: str, *, now: datetime) -> IngestCheckpoint:
        checkpoint = self.load(source_platform)
        updated = checkpoint.model_copy(update={"last_run_started_at": now})
        return self.save(updated)

    def advance_cursor(
        self,
        source_platform: str,
        *,
        cursor: str | None,
        seen_delta: int = 0,
        new_delta: int = 0,
        duplicate_delta: int = 0,
    ) -> IngestCheckpoint:
        checkpoint = self.load(source_platform)
        updated = checkpoint.model_copy(
            update={
                "cursor": cursor,
                "postings_seen": checkpoint.postings_seen + seen_delta,
                "postings_new": checkpoint.postings_new + new_delta,
                "postings_duplicate": checkpoint.postings_duplicate + duplicate_delta,
            }
        )
        return self.save(updated)

    def complete_run(self, source_platform: str, *, now: datetime) -> IngestCheckpoint:
        checkpoint = self.load(source_platform)
        if checkpoint.last_run_started_at is None:
            raise CheckpointError(
                f"cannot complete a run for {source_platform!r} that never started"
            )
        updated = checkpoint.model_copy(update={"last_run_completed_at": now})
        return self.save(updated)
