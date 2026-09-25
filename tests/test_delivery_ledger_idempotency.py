from __future__ import annotations

from uuid import uuid4

from jobpilot.chat.ledger import DeliveryLedger
from jobpilot.db.repositories.conversations import OutboundDeliveryRepository
from jobpilot.integrations.supabase_client import InMemoryDatabase


def test_deliver_records_a_new_message():
    db = InMemoryDatabase()
    ledger = DeliveryLedger(OutboundDeliveryRepository(db))
    conversation_id = uuid4()

    result = ledger.deliver(
        conversation_id=conversation_id, idempotency_key="conv:msg1", body="Hello"
    )
    assert result is not None
    assert ledger.was_delivered("conv:msg1") is True


def test_deliver_is_idempotent_for_repeated_key():
    db = InMemoryDatabase()
    ledger = DeliveryLedger(OutboundDeliveryRepository(db))
    conversation_id = uuid4()

    first = ledger.deliver(
        conversation_id=conversation_id, idempotency_key="conv:msg1", body="Hello"
    )
    second = ledger.deliver(
        conversation_id=conversation_id, idempotency_key="conv:msg1", body="Hello again"
    )
    assert first is not None
    assert second is None  # duplicate suppressed, not a second send


def test_was_delivered_false_for_unknown_key():
    db = InMemoryDatabase()
    ledger = DeliveryLedger(OutboundDeliveryRepository(db))
    assert ledger.was_delivered("never-sent") is False
