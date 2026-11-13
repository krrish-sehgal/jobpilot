"""Streaming one agent turn to the browser as server-sent events.

How a chat turn flows:

1. `POST /conversations/{id}/messages` persists the user's message and
   returns `{message_id, turn_id}`. Nothing has been processed yet; the
   message is durable (the same guarantee the webhook channel gives).
2. `GET .../turns/{turn_id}/stream` calls `TurnStreamer.open` (which
   validates ownership and returns proper JSON errors *before* the
   response starts) and then streams `TurnStreamer.events`.
3. The turn runs on a worker thread through the existing
   `TurnOrchestrator`, so the lease and delivery-ledger guarantees still
   apply. The agent loop's `on_event` hook feeds a queue; the HTTP
   generator drains it. The worker, not the HTTP connection, persists the
   reply, so a closed tab does not lose the answer, and reconnecting to
   the same turn replays it from storage instead of running it twice.

Tokens: the model client used here returns a whole reply, so the final
text is cut into `token` events after it is ready. That keeps the wire
contract identical to a provider with native streaming, where the same
events would instead be forwarded delta by delta as they arrive.
"""

from __future__ import annotations

import json
import queue
import re
import threading
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from jobpilot.agent.events import AgentEvent
from jobpilot.agent.tools import AgentToolContext
from jobpilot.chat.orchestrator import TurnOrchestrator
from jobpilot.db.repositories.conversations import MessageRepository
from jobpilot.logging import get_logger
from jobpilot.models import Message, MessageDirection, MessageStatus, UserAccount

logger = get_logger(__name__)

KEEPALIVE_SECONDS = 15.0
TOKEN_CHUNK_CHARS = 24

ContextFactory = Callable[[UserAccount, UUID], AgentToolContext]


def format_sse(event: str, data: dict[str, Any]) -> str:
    """One SSE frame: `event:` line, single-line JSON `data:` line, blank line.

    `json.dumps` never emits a raw newline (they are escaped), so the data
    always fits one `data:` line, which is what every SSE parser handles.
    """

    return (
        f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, separators=(',', ':'))}\n\n"
    )


def chunk_text(text: str, size: int = TOKEN_CHUNK_CHARS) -> list[str]:
    """Split `text` into chunks of about `size` characters at word boundaries.

    Whitespace stays attached to the chunk it follows, so
    `"".join(chunk_text(t)) == t` exactly and the client can append
    chunks without adding separators.
    """

    pieces = re.findall(r"\S+\s*|\s+", text)
    chunks: list[str] = []
    current = ""
    for piece in pieces:
        if current and len(current) + len(piece) > size:
            chunks.append(current)
            current = ""
        current += piece
        while len(current) > size * 2:  # a single enormous "word"
            chunks.append(current[:size])
            current = current[size:]
    if current:
        chunks.append(current)
    return chunks


@dataclass(frozen=True)
class TurnHandle:
    """A validated request to stream one turn."""

    user: UserAccount
    conversation_id: UUID
    user_message: Message
    reply: Message | None


_DONE = object()


class TurnStreamer:
    def __init__(
        self,
        *,
        messages: MessageRepository,
        orchestrator: TurnOrchestrator,
        context_factory: ContextFactory,
        keepalive_seconds: float = KEEPALIVE_SECONDS,
    ) -> None:
        self._messages = messages
        self._orchestrator = orchestrator
        self._context_factory = context_factory
        self._keepalive = keepalive_seconds

    def open(self, user: UserAccount, conversation_id: UUID, turn_id: UUID) -> TurnHandle:
        """Look up the turn. Raises `RecordNotFoundError` (-> 404) if absent.

        The conversation must already have been checked as owned by
        `user`; turn ids are only unique within it.
        """

        user_message, reply = self._messages.find_turn(conversation_id, turn_id)
        return TurnHandle(user, conversation_id, user_message, reply)

    def events(self, handle: TurnHandle) -> Iterator[str]:
        if handle.reply is not None:
            yield from self._replay(handle.reply)
            return
        status = handle.user_message.status
        if status is MessageStatus.FAILED:
            yield self._error("turn_failed", "this message could not be answered", True)
            return
        if status is MessageStatus.PROCESSING:
            yield self._error("turn_in_progress", "this turn is already running", True)
            return

        channel: queue.Queue[Any] = queue.Queue()
        threading.Thread(
            target=self._run, args=(handle, channel), daemon=True, name="chat-turn"
        ).start()
        while True:
            try:
                item = channel.get(timeout=self._keepalive)
            except queue.Empty:
                yield ": keep-alive\n\n"  # a comment frame; keeps proxies from idling out
                continue
            if item is _DONE:
                return
            yield item

    # --- worker ----------------------------------------------------------

    def _run(self, handle: TurnHandle, channel: queue.Queue[Any]) -> None:
        try:
            self._run_turn(handle, channel)
        except Exception:
            logger.exception("chat_turn_failed", conversation_id=str(handle.conversation_id))
            channel.put(self._error("turn_failed", "something went wrong, please try again", True))
        finally:
            channel.put(_DONE)

    def _run_turn(self, handle: TurnHandle, channel: queue.Queue[Any]) -> None:
        ctx = self._context_factory(handle.user, handle.conversation_id)

        def on_event(event: AgentEvent) -> None:
            channel.put(format_sse(event.kind, event.data))
            result = event.result
            started = (
                event.kind == "tool_result"
                and event.data["name"] == "tailor_resume"
                and isinstance(result, dict)
                and result.get("started")
            )
            if started:
                channel.put(
                    format_sse(
                        "tailoring_started",
                        {"tailoring_id": result["tailoring_id"], "job_id": result["job_id"]},
                    )
                )

        reply_text = self._orchestrator.process_turn(
            handle.conversation_id, handle.user_message.id, ctx, on_event=on_event
        )
        if reply_text is None:
            # Another worker holds the lease: that run will persist the reply.
            channel.put(self._error("turn_in_progress", "this turn is already running", True))
            return

        # Narrow race: a second stream for the same turn may have finished
        # between our status check and the lease claim. Never write twice.
        _, already = self._messages.find_turn(handle.conversation_id, handle.user_message.turn_id)
        if already is not None:
            for frame in self._reply_frames(already):
                channel.put(frame)
            return

        tailorings = ctx.artifacts.tailorings
        reply = self._messages.save(
            Message(
                conversation_id=handle.conversation_id,
                user_id=handle.user.id,
                direction=MessageDirection.OUTBOUND,
                body=reply_text,
                status=MessageStatus.PROCESSED,
                turn_id=handle.user_message.turn_id,
                job_cards=ctx.artifacts.job_cards,
                tailoring_id=UUID(tailorings[-1]["tailoring_id"]) if tailorings else None,
            )
        )
        for frame in self._reply_frames(reply):
            channel.put(frame)

    # --- shared frames -----------------------------------------------------

    def _replay(self, reply: Message) -> Iterator[str]:
        """Re-send a finished reply (reconnect, or a second tab)."""

        yield format_sse("status", {"phase": "writing"})
        yield from self._reply_frames(reply)

    @staticmethod
    def _reply_frames(reply: Message) -> Iterator[str]:
        for chunk in chunk_text(reply.body):
            yield format_sse("token", {"text": chunk})
        if reply.job_cards:
            yield format_sse("job_cards", {"cards": reply.job_cards})
        yield format_sse("done", {"message_id": str(reply.id)})

    @staticmethod
    def _error(code: str, message: str, retryable: bool) -> str:
        return format_sse("error", {"code": code, "message": message, "retryable": retryable})
