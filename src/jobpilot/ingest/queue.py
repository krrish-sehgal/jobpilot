"""
A stub queue sitting between scraping and enrichment.

The point of the queue is to decouple the two: a scraper can run on
its own schedule and dump raw postings without waiting for anything to
process them, and a worker can consume at its own pace (or several
workers can consume in parallel) without caring which scraper produced
what it's working on. Neither side needs to know how busy the other is.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class QueueMessage:
    """Wraps a reference to one raw posting sitting in object storage,
    not the posting body itself — queues are for pointers and small
    metadata, not for bulk data."""

    message_id: str
    storage_key: str
    source_ats: str


def push(storage_key: str, *, source_ats: str) -> QueueMessage:
    """Enqueue a pointer to a raw posting that was just written to
    object storage, so a worker can pick it up for enrichment.
    """
    raise NotImplementedError("demo only: no real queue is connected")


def pop(*, visibility_timeout_seconds: int = 60) -> QueueMessage | None:
    """Pop the next available message for a worker to process.

    A real queue would hide the message from other consumers for
    `visibility_timeout_seconds` while this worker processes it, then
    either delete it (on success, via ack) or let it reappear (on
    failure/timeout) so another worker can retry it.

    Returns None if the queue is currently empty.
    """
    raise NotImplementedError("demo only: no real queue is connected")


def ack(message_id: str) -> None:
    """Confirm a message was processed successfully and can be removed
    from the queue permanently."""
    raise NotImplementedError("demo only: no real queue is connected")
