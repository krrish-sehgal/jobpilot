"""The two long-running loops of ingestion: `ScraperRunner` (scraper ->
object storage -> queue) and `EnrichmentWorker` (queue -> LLM -> jobs
table).

Splitting scraping from enrichment across a queue means a slow LLM
call never blocks a scraper's rate-limited crawl, and a burst of new
postings queues up for enrichment to drain at its own pace instead of
backing up the scraper.
"""

from __future__ import annotations

from jobpilot.db.repositories.jobs import JobRepository
from jobpilot.errors import DuplicatePostingError, EnrichmentError, ScraperError
from jobpilot.ingest.checkpoint import CheckpointStore
from jobpilot.ingest.dedup import Deduplicator
from jobpilot.ingest.enrich import enrich_posting
from jobpilot.ingest.queue import IngestQueue
from jobpilot.ingest.scrapers.base import BaseScraper
from jobpilot.integrations.llm import LLMClient
from jobpilot.integrations.storage import ObjectStorage
from jobpilot.logging import get_logger
from jobpilot.models import RawPosting

logger = get_logger(__name__)


class ScraperRunner:
    """Drives a single scraper to completion, checkpointing as it goes.

    Each page fetched is: deduplicated against `Deduplicator`, written
    to object storage as the durable raw record, published to the
    ingestion queue for enrichment, and checkpointed — in that order,
    so a crash between any two steps loses at most one in-flight page
    rather than corrupting already-committed state.
    """

    def __init__(
        self,
        scraper: BaseScraper,
        *,
        queue: IngestQueue,
        storage: ObjectStorage,
        checkpoints: CheckpointStore,
        deduplicator: Deduplicator,
        now,
    ) -> None:
        self._scraper = scraper
        self._queue = queue
        self._storage = storage
        self._checkpoints = checkpoints
        self._dedup = deduplicator
        self._now = now

    def run(self, *, max_pages: int | None = None) -> dict[str, int]:
        platform = self._scraper.platform_name
        checkpoint = self._checkpoints.start_run(platform, now=self._now())
        cursor = checkpoint.cursor

        pages_processed = 0
        totals = {"seen": 0, "new": 0, "duplicate": 0}

        for page in self._scraper.iter_all_pages(start_cursor=cursor):
            page_totals = self._process_page(page.postings)
            for key in totals:
                totals[key] += page_totals[key]

            self._checkpoints.advance_cursor(
                platform,
                cursor=page.next_cursor,
                seen_delta=page_totals["seen"],
                new_delta=page_totals["new"],
                duplicate_delta=page_totals["duplicate"],
            )

            pages_processed += 1  # noqa: SIM113 (also used for max_pages comparison below)
            if max_pages is not None and pages_processed >= max_pages:
                break
            if not page.has_more:
                break

        self._checkpoints.complete_run(platform, now=self._now())
        logger.info("scraper_run_complete", platform=platform, **totals)
        return totals

    def _process_page(self, postings: list[RawPosting]) -> dict[str, int]:
        totals = {"seen": 0, "new": 0, "duplicate": 0}
        for posting in postings:
            totals["seen"] += 1
            try:
                self._dedup.check(posting)
            except DuplicatePostingError:
                totals["duplicate"] += 1
                continue

            storage_key = f"raw-postings/{posting.source_platform}/{posting.content_hash}.json"
            self._storage.put(storage_key, posting.model_dump_json().encode("utf-8"))
            self._queue.publish(posting)
            self._dedup.mark_seen(posting)
            totals["new"] += 1
        return totals


class EnrichmentWorker:
    """Drains the ingestion queue, enriches each posting, and saves it.

    A posting that fails enrichment (a malformed LLM response, a
    taxonomy violation) is logged and left un-acknowledged so the
    queue backend's visibility timeout returns it for a bounded number
    of retries before it lands in the dead-letter path.
    """

    def __init__(
        self,
        *,
        queue: IngestQueue,
        llm: LLMClient,
        jobs: JobRepository,
        deduplicator: Deduplicator,
    ) -> None:
        self._queue = queue
        self._llm = llm
        self._jobs = jobs
        self._dedup = deduplicator

    def drain_once(self, *, max_messages: int = 10) -> dict[str, int]:
        totals = {"enriched": 0, "duplicate": 0, "failed": 0}
        for message, posting in self._queue.poll(max_messages=max_messages):
            try:
                if self._dedup.is_duplicate(posting):
                    totals["duplicate"] += 1
                    self._queue.acknowledge(message)
                    continue

                job = enrich_posting(self._llm, posting)
                self._jobs.save(job)
                self._dedup.mark_seen(posting)
                self._queue.acknowledge(message)
                totals["enriched"] += 1
            except EnrichmentError as exc:
                logger.warning(
                    "enrichment_failed",
                    source_platform=posting.source_platform,
                    content_hash=posting.content_hash,
                    error=str(exc),
                )
                totals["failed"] += 1
            except ScraperError as exc:
                logger.warning("posting_malformed", error=str(exc))
                totals["failed"] += 1
        return totals
