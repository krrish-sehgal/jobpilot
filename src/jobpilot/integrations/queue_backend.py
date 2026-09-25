"""Queue boundary between scraping and enrichment.

Decoupling scraping from enrichment through a queue lets the two
scale independently: scrapers burst when a platform's listing pages
change, while enrichment workers drain at a steady LLM-bound rate.
`QueueBackend` is the protocol; `InMemoryQueueBackend` is a faithful
enough fake (visibility timeout, receive-count tracking, redelivery)
to exercise `jobpilot.ingest.worker` in tests without a real broker.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from jobpilot.config import Settings
from jobpilot.errors import QueueError


@dataclass
class QueueMessage:
    id: str
    body: str
    receive_count: int = 0


class QueueBackend(Protocol):
    def send(self, body: str) -> str: ...

    def receive(self, max_messages: int = 1) -> list[QueueMessage]: ...

    def delete(self, message_id: str) -> None: ...

    def queue_depth(self) -> int: ...


class HTTPQueueBackend:
    """Real queue client. Unconfigured until a queue URL is set."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _require_real_config(self) -> None:
        if self._settings.queue_url.startswith("https://queue.example.com"):
            raise QueueError("no queue configured (JOBPILOT_QUEUE_URL is still a placeholder)")

    def send(self, body: str) -> str:
        self._require_real_config()
        raise QueueError("HTTPQueueBackend is not wired to a live queue in this environment")

    def receive(self, max_messages: int = 1) -> list[QueueMessage]:
        self._require_real_config()
        raise QueueError("HTTPQueueBackend is not wired to a live queue in this environment")

    def delete(self, message_id: str) -> None:
        self._require_real_config()
        raise QueueError("HTTPQueueBackend is not wired to a live queue in this environment")

    def queue_depth(self) -> int:
        self._require_real_config()
        raise QueueError("HTTPQueueBackend is not wired to a live queue in this environment")


@dataclass
class _InFlightMessage:
    message: QueueMessage
    visible_at: float


@dataclass
class InMemoryQueueBackend:
    """In-memory FIFO queue with visibility-timeout semantics.

    A received message becomes invisible to other `receive()` calls
    until `visibility_timeout_seconds` elapses or it is explicitly
    deleted, mirroring at-least-once delivery queues like SQS closely
    enough to test redelivery and max-receive-count handling.
    """

    visibility_timeout_seconds: float = 30.0
    max_receive_count: int = 5
    clock: Callable[[], float] = time.monotonic

    _pending: list[QueueMessage] = field(default_factory=list)
    _in_flight: dict[str, _InFlightMessage] = field(default_factory=dict)
    _dead_letters: list[QueueMessage] = field(default_factory=list)

    def send(self, body: str) -> str:
        message = QueueMessage(id=str(uuid.uuid4()), body=body)
        self._pending.append(message)
        return message.id

    def receive(self, max_messages: int = 1) -> list[QueueMessage]:
        self._reclaim_expired()
        received: list[QueueMessage] = []
        while self._pending and len(received) < max_messages:
            message = self._pending.pop(0)
            message.receive_count += 1
            if message.receive_count > self.max_receive_count:
                self._dead_letters.append(message)
                continue
            self._in_flight[message.id] = _InFlightMessage(
                message=message,
                visible_at=self.clock() + self.visibility_timeout_seconds,
            )
            received.append(message)
        return received

    def delete(self, message_id: str) -> None:
        self._in_flight.pop(message_id, None)

    def queue_depth(self) -> int:
        self._reclaim_expired()
        return len(self._pending)

    @property
    def dead_letters(self) -> list[QueueMessage]:
        return list(self._dead_letters)

    def _reclaim_expired(self) -> None:
        now = self.clock()
        expired_ids = [
            mid for mid, in_flight in self._in_flight.items() if in_flight.visible_at <= now
        ]
        for mid in expired_ids:
            in_flight = self._in_flight.pop(mid)
            self._pending.append(in_flight.message)
