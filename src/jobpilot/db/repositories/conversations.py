"""Repository for messages, turn leases, and outbound deliveries.

Grouped into one module because all three exist to support the same
durable-conversation guarantee described in `docs/architecture.md`:
persist before processing, lease before working, dedupe before
sending.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from jobpilot.errors import DuplicateDeliveryError, RecordNotFoundError, TurnLeaseConflictError
from jobpilot.integrations.supabase_client import Database
from jobpilot.models import Message, MessageStatus, OutboundDelivery, TurnLease

_MESSAGES_TABLE = "messages"
_LEASES_TABLE = "turn_leases"
_DELIVERIES_TABLE = "outbound_deliveries"


class MessageRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def save(self, message: Message) -> Message:
        row = self._db.insert(_MESSAGES_TABLE, message.model_dump(mode="json"))
        return Message.model_validate(row)

    def get(self, message_id: UUID) -> Message:
        row = self._db.get(_MESSAGES_TABLE, str(message_id))
        return Message.model_validate(row)

    def update_status(self, message_id: UUID, status: MessageStatus) -> Message:
        row = self._db.update(_MESSAGES_TABLE, str(message_id), {"status": status.value})
        return Message.model_validate(row)

    def list_for_conversation(self, conversation_id: UUID) -> list[Message]:
        rows = self._db.find(_MESSAGES_TABLE, conversation_id=str(conversation_id))
        messages = [Message.model_validate(row) for row in rows]
        return sorted(messages, key=lambda m: m.created_at)


class TurnLeaseRepository:
    """Claim-and-lease store preventing two workers processing one turn.

    A lease is keyed by `conversation_id`; `claim` fails with
    `TurnLeaseConflictError` if an unexpired lease already exists,
    which is what stops a second worker (or a retried delivery) from
    racing an in-flight turn.
    """

    def __init__(self, db: Database) -> None:
        self._db = db

    def claim(self, lease: TurnLease, *, now: datetime) -> TurnLease:
        key = str(lease.conversation_id)
        try:
            existing_row = self._db.get(_LEASES_TABLE, key)
        except RecordNotFoundError:
            existing_row = None

        if existing_row is not None:
            existing = TurnLease.model_validate(existing_row)
            if existing.expires_at > now:
                raise TurnLeaseConflictError(
                    f"conversation {lease.conversation_id} already leased by "
                    f"{existing.worker_id!r} until {existing.expires_at.isoformat()}"
                )

        row = dict(lease.model_dump(mode="json"))
        row["id"] = key
        if existing_row is None:
            self._db.insert(_LEASES_TABLE, row)
        else:
            self._db.update(_LEASES_TABLE, key, row)
        return lease

    def release(self, conversation_id: UUID) -> None:
        self._db.delete(_LEASES_TABLE, str(conversation_id))

    def current(self, conversation_id: UUID) -> TurnLease | None:
        try:
            row = self._db.get(_LEASES_TABLE, str(conversation_id))
        except RecordNotFoundError:
            return None
        return TurnLease.model_validate(row)


class OutboundDeliveryRepository:
    """Idempotency ledger for outbound messages.

    `record` raises `DuplicateDeliveryError` if `idempotency_key` has
    already been recorded, so a retried send (e.g. after a timeout
    whose response was lost) never results in the user receiving the
    same reply twice.
    """

    def __init__(self, db: Database) -> None:
        self._db = db

    def record(self, delivery: OutboundDelivery) -> OutboundDelivery:
        existing = self._db.find(_DELIVERIES_TABLE, idempotency_key=delivery.idempotency_key)
        if existing:
            raise DuplicateDeliveryError(delivery.idempotency_key)
        row = self._db.insert(_DELIVERIES_TABLE, delivery.model_dump(mode="json"))
        return OutboundDelivery.model_validate(row)

    def was_delivered(self, idempotency_key: str) -> bool:
        return bool(self._db.find(_DELIVERIES_TABLE, idempotency_key=idempotency_key))
