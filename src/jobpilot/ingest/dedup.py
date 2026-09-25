"""Content-hash deduplication.

`Deduplicator` tracks which content hashes have already been ingested
and raises `DuplicatePostingError` for a repeat, so the queue consumer
can skip enrichment (an LLM call — not free) entirely for postings it
has already processed, regardless of which platform or listing id
they arrived under this time.
"""

from __future__ import annotations

from jobpilot.db.repositories.jobs import JobRepository
from jobpilot.errors import DuplicatePostingError
from jobpilot.models import RawPosting


class Deduplicator:
    def __init__(self, job_repository: JobRepository) -> None:
        self._jobs = job_repository
        self._seen_this_run: set[str] = set()

    def check(self, posting: RawPosting) -> None:
        """Raise `DuplicatePostingError` if this content has been seen
        before, either earlier in the current run or in a prior run
        (i.e. already persisted as a `JobRecord`)."""

        if posting.content_hash in self._seen_this_run:
            raise DuplicatePostingError(posting.content_hash)

        existing = self._jobs.find_by_content_hash(posting.content_hash)
        if existing is not None:
            raise DuplicatePostingError(posting.content_hash, existing_job_id=str(existing.id))

    def mark_seen(self, posting: RawPosting) -> None:
        self._seen_this_run.add(posting.content_hash)

    def is_duplicate(self, posting: RawPosting) -> bool:
        try:
            self.check(posting)
        except DuplicatePostingError:
            return True
        return False
