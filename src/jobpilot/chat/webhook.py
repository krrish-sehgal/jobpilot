"""
Inbound chat webhook.

The idea being demonstrated here is "durable turns": the very first
thing that happens when a message arrives is that it gets written to
the database, before any agent processing starts. If the process
crashes partway through handling a message, the message itself is
never lost — it's sitting in the database waiting to be picked up
again, rather than only existing in memory.

This is a generic "chat platform" webhook. It is deliberately not
wired to any specific messaging provider; imagine it as the kind of
endpoint any chat platform's webhook would call.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class InboundMessage:
    """The shape of a message as the chat platform would deliver it."""

    platform_message_id: str
    chat_user_id: str
    text: str
    received_at: datetime


def verify_webhook_signature(raw_body: bytes, signature_header: str, verify_token: str) -> bool:
    """Check that an inbound webhook call actually came from the chat
    platform, not from anyone who found the URL.

    Real chat platforms sign their webhook payloads with a shared
    secret (verify_token); the handler is expected to recompute the
    signature and compare it before trusting the body at all.
    """
    raise NotImplementedError("demo only: no real chat platform is wired up")


def persist_inbound_message(message: InboundMessage) -> str:
    """Write the inbound message to the database as the FIRST step of
    handling it, before any agent processing.

    This is what makes a turn durable: even if everything downstream of
    this call crashes, the message already exists in the `messages`
    table (see db/schema.sql) and can be picked up again by
    orchestrator.claim_next_turn instead of being lost.

    Returns the new message's id.
    """
    raise NotImplementedError("demo only: no real database is connected")


def handle_webhook_request(raw_body: bytes, signature_header: str) -> int:
    """Entry point a web framework route would call.

    Order of operations, matching the durable-turns idea:
      1. verify_webhook_signature — reject anything not from the platform
      2. parse raw_body into an InboundMessage
      3. persist_inbound_message — write it down BEFORE any processing
      4. return 200 immediately

    Processing the message (running the agent loop, sending a reply)
    happens out of band, picked up by orchestrator.claim_next_turn. The
    webhook handler's only job is to acknowledge receipt quickly and
    make sure nothing is lost if something downstream fails.

    Returns the HTTP status code that would be sent back to the chat
    platform.
    """
    raise NotImplementedError("demo only: see docstring for the intended request flow")
