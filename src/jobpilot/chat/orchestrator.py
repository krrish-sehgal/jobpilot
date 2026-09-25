"""
Turn orchestration: deciding which stored message to process next, and
making sure only one worker ever replies to a given message.

The idea being demonstrated: if you run more than one worker process
(for throughput, or just for redundancy), two workers could in theory
both pick up the same unprocessed message and both send a reply. The
claim-and-lease pattern below avoids that without needing a separate
distributed lock service — it uses a lease column on the row itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

DEFAULT_LEASE_DURATION = timedelta(seconds=30)
"""How long a worker holds exclusive claim on a message before another
worker is allowed to assume it died and pick the message up instead."""


@dataclass
class ClaimedTurn:
    """A message this worker has successfully claimed and may now
    process, plus the lease that gives it exclusivity."""

    message_id: str
    chat_user_id: str
    text: str
    lease_expires_at: datetime


def claim_next_turn(worker_id: str, *, lease_duration: timedelta = DEFAULT_LEASE_DURATION) -> ClaimedTurn | None:
    """Atomically claim the oldest unprocessed message that no other
    worker currently holds a live lease on.

    The intended implementation is a single conditional UPDATE against
    the `messages` table, something like:

        UPDATE messages
        SET claimed_by = :worker_id, lease_expires_at = now() + :lease_duration
        WHERE id = (
            SELECT id FROM messages
            WHERE status = 'pending'
              AND (lease_expires_at IS NULL OR lease_expires_at < now())
            ORDER BY received_at ASC
            LIMIT 1
            FOR UPDATE SKIP LOCKED
        )
        RETURNING id, chat_user_id, text;

    The "claimed_by + lease_expires_at" pair is the whole trick: a
    second worker's identical query simply won't match this row until
    the lease expires, so two workers can never both claim it while the
    first is still (presumably) working on it. If the first worker
    crashes, the lease eventually expires and the message becomes
    claimable again — nothing is lost, and nothing is double-replied.

    Returns None if there is nothing pending to claim.
    """
    raise NotImplementedError("demo only: no real database is connected")


def mark_turn_complete(message_id: str, *, reply_text: str) -> None:
    """Mark a claimed message as processed and record the reply that
    was sent for it. Called after the agent loop has produced an
    answer and it has been sent back over the chat platform.
    """
    raise NotImplementedError("demo only: no real database is connected")


def release_expired_leases() -> int:
    """Housekeeping pass: find messages whose lease has expired without
    being marked complete (the worker that claimed them presumably
    crashed or hung) and make them claimable again.

    Returns the number of leases released.
    """
    raise NotImplementedError("demo only: no real database is connected")
