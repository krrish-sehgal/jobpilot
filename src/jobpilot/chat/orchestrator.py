"""Turn orchestrator: claim-and-lease processing of a conversation turn.

Two workers (an autoscaled pool, or a retried background job) might
both pick up the same pending message. `TurnOrchestrator.process_turn`
claims a lease on the conversation before doing any work; a second
worker's claim fails with `TurnLeaseConflictError` while the lease is
held, which is what guarantees only one reply gets generated per turn.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from jobpilot.agent.loop import AgentLoop
from jobpilot.agent.tools import AgentToolContext
from jobpilot.chat.ledger import DeliveryLedger
from jobpilot.db.repositories.conversations import MessageRepository, TurnLeaseRepository
from jobpilot.errors import TurnLeaseConflictError
from jobpilot.logging import get_logger
from jobpilot.models import MessageStatus, TurnLease

logger = get_logger(__name__)


class TurnOrchestrator:
    def __init__(
        self,
        *,
        messages: MessageRepository,
        leases: TurnLeaseRepository,
        ledger: DeliveryLedger,
        agent_loop: AgentLoop,
        lease_seconds: int = 45,
        worker_id: str = "worker-1",
        clock=lambda: datetime.now(UTC),
    ) -> None:
        self._messages = messages
        self._leases = leases
        self._ledger = ledger
        self._agent_loop = agent_loop
        self._lease_seconds = lease_seconds
        self._worker_id = worker_id
        self._clock = clock

    def process_turn(
        self, conversation_id: UUID, message_id: UUID, ctx: AgentToolContext
    ) -> str | None:
        """Process one pending inbound message end to end.

        Returns the reply text that was recorded for delivery, or
        `None` if this worker lost the race to claim the lease (which
        is the expected, non-error outcome of a double-delivery).
        """

        now = self._clock()
        lease = TurnLease(
            conversation_id=conversation_id,
            worker_id=self._worker_id,
            claimed_at=now,
            expires_at=now + timedelta(seconds=self._lease_seconds),
        )

        try:
            self._leases.claim(lease, now=now)
        except TurnLeaseConflictError:
            logger.info("turn_lease_conflict", conversation_id=str(conversation_id))
            return None

        try:
            message = self._messages.get(message_id)
            self._messages.update_status(message_id, MessageStatus.PROCESSING)

            turn = self._agent_loop.run(ctx, message.body)
            reply_text = turn.final_reply or ""

            idempotency_key = f"{conversation_id}:{message_id}"
            self._ledger.deliver(
                conversation_id=conversation_id, idempotency_key=idempotency_key, body=reply_text
            )

            self._messages.update_status(message_id, MessageStatus.PROCESSED)
            return reply_text
        except Exception:
            self._messages.update_status(message_id, MessageStatus.FAILED)
            raise
        finally:
            self._leases.release(conversation_id)
