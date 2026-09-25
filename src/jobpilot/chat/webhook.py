"""Inbound webhook handler.

The handler's only responsibilities are: verify the request came from
the configured channel provider, persist the inbound message, and
return quickly. The agent loop is deliberately kept out of this path —
it happens in `jobpilot.chat.orchestrator`, invoked out-of-band (a
background task or a worker polling for unprocessed messages), so a
slow LLM turn never holds a webhook connection open and risks the
provider retrying (and duplicating) the delivery.
"""

from __future__ import annotations

import hashlib
import hmac
from uuid import UUID

from fastapi import APIRouter, FastAPI, HTTPException, Request
from pydantic import BaseModel

from jobpilot.config import Settings
from jobpilot.db.repositories.conversations import MessageRepository
from jobpilot.errors import SignatureVerificationError
from jobpilot.logging import get_logger
from jobpilot.models import Message, MessageDirection

logger = get_logger(__name__)


def verify_signature(*, payload: bytes, signature_header: str | None, signing_secret: str) -> None:
    """Verify an HMAC-SHA256 signature over the raw request body.

    Raises `SignatureVerificationError` if the header is missing or
    does not match. Uses `hmac.compare_digest` to avoid a timing
    side-channel on the comparison.
    """

    if not signature_header:
        raise SignatureVerificationError("missing signature header")

    expected = hmac.new(signing_secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    provided = signature_header.removeprefix("sha256=")
    if not hmac.compare_digest(expected, provided):
        raise SignatureVerificationError("signature does not match payload")


class InboundWebhookPayload(BaseModel):
    conversation_id: UUID
    user_id: UUID
    body: str


def build_webhook_router(settings: Settings, message_repository: MessageRepository) -> APIRouter:
    router = APIRouter()

    @router.post("/webhooks/inbound-message")
    async def receive_inbound_message(request: Request) -> dict:
        raw_body = await request.body()
        signature_header = request.headers.get("X-JobPilot-Signature")

        try:
            verify_signature(
                payload=raw_body,
                signature_header=signature_header,
                signing_secret=settings.webhook_signing_secret,
            )
        except SignatureVerificationError as exc:
            logger.warning("webhook_signature_rejected", error=str(exc))
            raise HTTPException(status_code=401, detail="invalid signature") from exc

        payload = InboundWebhookPayload.model_validate_json(raw_body)

        # Persist before anything else touches this message: if the
        # process crashes on the next line, the message is already
        # durable and a later pass over "received" messages picks it
        # back up, instead of the inbound event being lost silently.
        message = Message(
            conversation_id=payload.conversation_id,
            user_id=payload.user_id,
            direction=MessageDirection.INBOUND,
            body=payload.body,
        )
        saved = message_repository.save(message)

        logger.info(
            "inbound_message_received",
            message_id=str(saved.id),
            conversation_id=str(saved.conversation_id),
        )
        return {"status": "received", "message_id": str(saved.id)}

    return router


def build_app(settings: Settings, message_repository: MessageRepository) -> FastAPI:
    app = FastAPI(title="JobPilot Webhook Service")
    app.include_router(build_webhook_router(settings, message_repository))

    @app.get("/healthz")
    async def healthz() -> dict:
        return {"status": "ok"}

    return app


def create_app() -> FastAPI:
    """No-argument app factory for `uvicorn --factory` / local `make run`.

    Wires up settings and the database from the environment. Not used
    by the test suite, which builds `build_app` directly against an
    in-memory database instead.
    """

    from jobpilot.config import get_settings
    from jobpilot.db.client import get_database

    settings = get_settings()
    db = get_database(settings)
    return build_app(settings, MessageRepository(db))
