"""Thin producer/consumer wrapper around `QueueBackend`.

Serializes `RawPosting`s to JSON for the queue and back, so scrapers
and the enrichment worker never touch `QueueBackend.send`/`receive`
directly — only `IngestQueue`, which keeps the wire format in one
place.
"""

from __future__ import annotations

from jobpilot.errors import ScraperParseError
from jobpilot.integrations.queue_backend import QueueBackend, QueueMessage
from jobpilot.models import RawPosting


class IngestQueue:
    def __init__(self, backend: QueueBackend) -> None:
        self._backend = backend

    def publish(self, posting: RawPosting) -> str:
        return self._backend.send(posting.model_dump_json())

    def poll(self, max_messages: int = 10) -> list[tuple[QueueMessage, RawPosting]]:
        messages = self._backend.receive(max_messages=max_messages)
        results = []
        for message in messages:
            try:
                posting = RawPosting.model_validate_json(message.body)
            except ValueError as exc:
                raise ScraperParseError(f"malformed queue message {message.id!r}") from exc
            results.append((message, posting))
        return results

    def acknowledge(self, message: QueueMessage) -> None:
        self._backend.delete(message.id)

    def depth(self) -> int:
        return self._backend.queue_depth()
