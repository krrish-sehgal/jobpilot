"""Outbound delivery ledger: idempotent sends.

`DeliveryLedger.deliver` records an outbound message keyed by an
idempotency key before considering it sent. If the same key is passed
again — a retried orchestrator run after a crash, a re-delivered
webhook — `OutboundDeliveryRepository.record` raises
`DuplicateDeliveryError`, which `deliver` treats as a no-op success
rather than sending (or re-recording) a duplicate reply.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from jobpilot.db.repositories.conversations import OutboundDeliveryRepository
from jobpilot.errors import DuplicateDeliveryError
from jobpilot.logging import get_logger
from jobpilot.models import OutboundDelivery

logger = get_logger(__name__)


class DeliveryLedger:
    def __init__(
        self, deliveries: OutboundDeliveryRepository, clock=lambda: datetime.now(UTC)
    ) -> None:
        self._deliveries = deliveries
        self._clock = clock

    def deliver(
        self, *, conversation_id: UUID, idempotency_key: str, body: str
    ) -> OutboundDelivery | None:
        delivery = OutboundDelivery(
            idempotency_key=idempotency_key,
            conversation_id=conversation_id,
            body=body,
            delivered_at=self._clock(),
        )
        try:
            return self._deliveries.record(delivery)
        except DuplicateDeliveryError:
            logger.info("duplicate_delivery_suppressed", idempotency_key=idempotency_key)
            return None

    def was_delivered(self, idempotency_key: str) -> bool:
        return self._deliveries.was_delivered(idempotency_key)
