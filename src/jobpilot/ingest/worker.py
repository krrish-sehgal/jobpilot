"""
The ingestion worker: consumes the queue, enriches each posting, and
writes the result to the search index (and the database).

This is the piece that decouples "collecting postings" from
"processing postings" — see queue.py for why that split exists. The
worker itself does very little on its own; it mostly wires together
queue.pop, enrich.enrich_posting, and a write to storage.
"""

from __future__ import annotations

from jobpilot.ingest import queue
from jobpilot.ingest.enrich import EnrichedJob, enrich_posting


def fetch_raw_posting(storage_key: str) -> str:
    """Fetch the raw posting body from object storage by key.

    The queue only carries a pointer (see queue.QueueMessage); the
    actual posting text lives in object storage and is fetched here
    just before enrichment.
    """
    raise NotImplementedError("demo only: no real object storage is connected")


def write_enriched_job(job: EnrichedJob) -> None:
    """Persist an enriched job record to the database and search index
    (see db/schema.sql for the `jobs` table this would land in)."""
    raise NotImplementedError("demo only: no real database is connected")


def process_one_message() -> bool:
    """Pop a single message off the queue, enrich it, and write the
    result. Returns False if the queue was empty (nothing to do).

    Intended control flow:

        message = queue.pop()
        if message is None:
            return False
        raw_text = fetch_raw_posting(message.storage_key)
        enriched = enrich_posting(raw_text)
        write_enriched_job(enriched)
        queue.ack(message.message_id)
        return True

    Left undone since none of the pieces it calls are wired to
    anything real in this demo.
    """
    raise NotImplementedError("demo only: see docstring for the intended control flow")


def run_forever() -> None:
    """What a long-running worker process would do: call
    process_one_message in a loop, with some backoff when the queue is
    empty. Not implemented for the same reason as everything else here.
    """
    raise NotImplementedError("demo only: no real queue is connected")
