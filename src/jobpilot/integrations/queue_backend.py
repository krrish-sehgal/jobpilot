"""Queue boundary between scraping and enrichment.

Decoupling scraping from enrichment through a queue lets the two
scale independently: scrapers burst when a platform's listing pages
change, while enrichment workers drain at a steady LLM-bound rate.
`QueueBackend` is the protocol; `InMemoryQueueBackend` is a faithful
enough test double (visibility timeout, receive-count tracking, redelivery)
to exercise `jobpilot.ingest.worker` in tests without a real broker.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from botocore.exceptions import BotoCoreError, ClientError

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


class SqsQueueBackend:
    """Amazon SQS-backed queue.

    `QueueMessage.id` carries the SQS receipt handle (what `delete`
    needs), while `send` returns the SQS message id. `receive_count`
    comes from `ApproximateReceiveCount`; dead-lettering is left to the
    queue's redrive policy. `boto3` is imported on construction, and a
    preconfigured client can be passed in instead.
    """

    def __init__(self, settings: Settings, *, client: Any | None = None) -> None:
        self._queue_url = settings.queue_url
        self._visibility_timeout = settings.queue_visibility_timeout_seconds
        if client is None:
            if settings.queue_url.startswith("https://queue.example.com"):
                raise QueueError("no queue configured (JOBPILOT_QUEUE_URL is still a placeholder)")
            import boto3

            client = boto3.client("sqs", region_name=settings.queue_region)
        self._client = client

    def send(self, body: str) -> str:
        try:
            response = self._client.send_message(QueueUrl=self._queue_url, MessageBody=body)
        except (BotoCoreError, ClientError) as exc:
            raise QueueError(f"could not send message: {exc}") from exc
        return str(response["MessageId"])

    def receive(self, max_messages: int = 1) -> list[QueueMessage]:
        try:
            response = self._client.receive_message(
                QueueUrl=self._queue_url,
                MaxNumberOfMessages=max(1, min(max_messages, 10)),
                VisibilityTimeout=self._visibility_timeout,
                AttributeNames=["ApproximateReceiveCount"],
                WaitTimeSeconds=0,
            )
        except (BotoCoreError, ClientError) as exc:
            raise QueueError(f"could not receive messages: {exc}") from exc
        return [
            QueueMessage(
                id=raw["ReceiptHandle"],
                body=raw["Body"],
                receive_count=int(raw.get("Attributes", {}).get("ApproximateReceiveCount", 1)),
            )
            for raw in response.get("Messages", [])
        ]

    def delete(self, message_id: str) -> None:
        """Delete a received message; `message_id` is its `QueueMessage.id`."""

        try:
            self._client.delete_message(QueueUrl=self._queue_url, ReceiptHandle=message_id)
        except (BotoCoreError, ClientError) as exc:
            raise QueueError(f"could not delete message: {exc}") from exc

    def queue_depth(self) -> int:
        try:
            response = self._client.get_queue_attributes(
                QueueUrl=self._queue_url, AttributeNames=["ApproximateNumberOfMessages"]
            )
        except (BotoCoreError, ClientError) as exc:
            raise QueueError(f"could not read queue depth: {exc}") from exc
        return int(response["Attributes"]["ApproximateNumberOfMessages"])


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
