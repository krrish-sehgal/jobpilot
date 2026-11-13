"""`/conversations/*`: list, create, history, post a message, stream a turn."""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from jobpilot.models import Message, MessageDirection
from jobpilot.web.deps import Container, CurrentUser, parse_id
from jobpilot.web.schemas import (
    ChatMessageOut,
    ConversationSummaryOut,
    CreateConversationBody,
    PostMessageBody,
    PostMessageResponse,
)

router = APIRouter(tags=["chat"])

_DEFAULT_TITLE = "New conversation"
_TITLE_CHARS = 60


@router.get("/conversations")
def list_conversations(container: Container, user: CurrentUser) -> list[ConversationSummaryOut]:
    return [
        container.conversations_presenter.summary(c)
        for c in container.conversations.list_for_user(user.id)
    ]


@router.post("/conversations", status_code=201)
def create_conversation(
    container: Container, user: CurrentUser, body: CreateConversationBody | None = None
) -> ConversationSummaryOut:
    conversation = container.conversations.create(user.id)
    return container.conversations_presenter.summary(conversation)


@router.get("/conversations/{conversation_id}/messages")
def list_messages(
    conversation_id: str, container: Container, user: CurrentUser
) -> list[ChatMessageOut]:
    conversation = container.conversations.get_for_user(user.id, parse_id(conversation_id))
    return container.conversations_presenter.messages(conversation, user)


@router.post("/conversations/{conversation_id}/messages", status_code=202)
def post_message(
    conversation_id: str, body: PostMessageBody, container: Container, user: CurrentUser
) -> PostMessageResponse:
    """Persist the message and hand back a turn id. Does not run the agent.

    Idempotent on `client_message_id`: a repeat returns the original ids
    and writes nothing, so a double click or a retried request can never
    start a second turn.
    """

    conversation = container.conversations.get_for_user(user.id, parse_id(conversation_id))
    message, created = container.messages.save_idempotent(
        Message(
            conversation_id=conversation.id,
            user_id=user.id,
            direction=MessageDirection.INBOUND,
            body=body.body,
            client_message_id=body.client_message_id,
            turn_id=uuid4(),
        )
    )
    if created:
        title = None
        if conversation.title == _DEFAULT_TITLE:
            title = " ".join(body.body.split())[:_TITLE_CHARS]
        container.conversations.touch(conversation.id, title=title)
    assert message.turn_id is not None  # always set by this route
    return PostMessageResponse(message_id=message.id, turn_id=message.turn_id)


@router.get("/conversations/{conversation_id}/turns/{turn_id}/stream")
def stream_turn(
    conversation_id: str, turn_id: str, container: Container, user: CurrentUser
) -> StreamingResponse:
    conversation = container.conversations.get_for_user(user.id, parse_id(conversation_id))
    # Resolved before the response starts, so a bad id is a normal JSON 404.
    handle = container.streamer.open(user, conversation.id, parse_id(turn_id))
    return StreamingResponse(
        container.streamer.events(handle),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",  # tell nginx not to buffer the stream
        },
    )
