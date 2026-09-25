from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from jobpilot.db.repositories.conversations import TurnLeaseRepository
from jobpilot.errors import TurnLeaseConflictError
from jobpilot.integrations.supabase_client import InMemoryDatabase
from jobpilot.models import TurnLease


def test_claim_succeeds_when_no_existing_lease():
    db = InMemoryDatabase()
    repo = TurnLeaseRepository(db)
    now = datetime.now(UTC)
    conversation_id = uuid4()
    lease = TurnLease(
        conversation_id=conversation_id,
        worker_id="w1",
        claimed_at=now,
        expires_at=now + timedelta(seconds=30),
    )
    repo.claim(lease, now=now)
    assert repo.current(conversation_id).worker_id == "w1"


def test_second_worker_cannot_claim_while_lease_is_live():
    db = InMemoryDatabase()
    repo = TurnLeaseRepository(db)
    now = datetime.now(UTC)
    conversation_id = uuid4()

    first = TurnLease(
        conversation_id=conversation_id,
        worker_id="w1",
        claimed_at=now,
        expires_at=now + timedelta(seconds=30),
    )
    repo.claim(first, now=now)

    second = TurnLease(
        conversation_id=conversation_id,
        worker_id="w2",
        claimed_at=now,
        expires_at=now + timedelta(seconds=30),
    )
    with pytest.raises(TurnLeaseConflictError):
        repo.claim(second, now=now)


def test_claim_succeeds_after_release():
    db = InMemoryDatabase()
    repo = TurnLeaseRepository(db)
    now = datetime.now(UTC)
    conversation_id = uuid4()

    first = TurnLease(
        conversation_id=conversation_id,
        worker_id="w1",
        claimed_at=now,
        expires_at=now + timedelta(seconds=30),
    )
    repo.claim(first, now=now)
    repo.release(conversation_id)

    second = TurnLease(
        conversation_id=conversation_id,
        worker_id="w2",
        claimed_at=now,
        expires_at=now + timedelta(seconds=30),
    )
    repo.claim(second, now=now)  # should not raise
    assert repo.current(conversation_id).worker_id == "w2"


def test_claim_succeeds_after_expiry_without_explicit_release():
    db = InMemoryDatabase()
    repo = TurnLeaseRepository(db)
    claimed_at = datetime.now(UTC)
    conversation_id = uuid4()

    first = TurnLease(
        conversation_id=conversation_id,
        worker_id="w1",
        claimed_at=claimed_at,
        expires_at=claimed_at + timedelta(seconds=10),
    )
    repo.claim(first, now=claimed_at)

    later = claimed_at + timedelta(seconds=11)
    second = TurnLease(
        conversation_id=conversation_id,
        worker_id="w2",
        claimed_at=later,
        expires_at=later + timedelta(seconds=30),
    )
    repo.claim(second, now=later)  # lease expired, so this should not raise
    assert repo.current(conversation_id).worker_id == "w2"
