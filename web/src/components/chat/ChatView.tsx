"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { describeError } from "@/lib/api/errors";
import type { ChatMessage } from "@/lib/api/types";
import { useChatStream } from "@/hooks/useChatStream";
import { useConversation } from "@/hooks/useConversation";
import { useConversationList } from "@/hooks/useConversationList";
import { clearPending, peekPending, setPending } from "@/lib/chat/pending";
import { uuid } from "@/lib/id";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { Skeleton } from "@/components/ui/Spinner";
import { Composer } from "./Composer";
import { MessageList } from "./MessageList";
import { StreamingBubble } from "./StreamingBubble";
import { SuggestedPrompts } from "./SuggestedPrompts";

/**
 * The chat screen for both routes. `conversationId === null` is the "new chat"
 * state at /app/chat; otherwise it is an existing thread.
 */
export function ChatView({ conversationId }: { conversationId: string | null }) {
  const router = useRouter();
  const { upsert, refresh } = useConversationList();
  const pending = conversationId ? peekPending(conversationId) : undefined;
  const { messages, loading, error, append, reload } = useConversation(conversationId, Boolean(pending));
  const [startError, setStartError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);

  const stream = useChatStream({
    onComplete: (message: ChatMessage) => {
      append(message);
      if (conversationId) clearPending(conversationId);
      void refresh(); // title / preview / ordering changed on the server
    },
  });

  const sendInThread = (id: string, body: string, clientMessageId: string = uuid()) => {
    // Optimistic user bubble; reusing the client id as its key de-dupes on retry.
    append({ id: clientMessageId, role: "user", body, job_cards: [], tailoring_id: null, created_at: new Date().toISOString() });
    stream.send(id, body, clientMessageId);
  };

  // First message of a new chat was handed off by the /app/chat page: send it now.
  // No "already started" guard on purpose: in dev, Strict Mode runs this effect twice and the
  // first run is aborted, so the second must resend. client_message_id makes that harmless.
  useEffect(() => {
    if (!conversationId || !pending) return;
    sendInThread(conversationId, pending.body, pending.clientMessageId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conversationId]);

  async function handleSend(body: string) {
    if (conversationId) return sendInThread(conversationId, body);
    // New chat: create the conversation, hand the message to the next page, navigate.
    setStarting(true);
    setStartError(null);
    try {
      const conv = await api.createConversation();
      upsert(conv);
      setPending(conv.id, { body, clientMessageId: uuid() });
      router.push(`/app/chat/${conv.id}`);
    } catch (e) {
      setStartError(describeError(e));
      setStarting(false);
    }
  }

  const empty = !loading && !error && !pending && messages.length === 0 && stream.state.status === "idle";
  const busy = stream.busy || starting;

  return (
    <div className="flex h-full flex-col">
      {loading ? (
        <div className="mx-auto w-full max-w-3xl space-y-4 px-4 py-6">
          <Skeleton className="ml-auto h-10 w-2/3" /><Skeleton className="h-24 w-full" />
        </div>
      ) : error ? (
        <div className="mx-auto w-full max-w-3xl p-6"><ErrorNotice message={error} onRetry={reload} /></div>
      ) : empty ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-6 px-4 text-center">
          <div>
            <h1 className="font-display text-4xl">Where should we fly today?</h1>
            <p className="mx-auto mt-3 max-w-md text-muted">Tell me the kind of role you want. I&apos;ll search, explain each match, and tailor your resume.</p>
          </div>
          <SuggestedPrompts onPick={handleSend} disabled={busy} />
        </div>
      ) : (
        <MessageList messages={messages} followKey={`${stream.state.text.length}:${stream.state.tools.length}:${stream.state.cards.length}:${stream.state.status}`}>
          <StreamingBubble state={stream.state} onRetry={stream.retry} />
        </MessageList>
      )}

      <div className="mx-auto w-full max-w-3xl px-4 pb-4 pt-2">
        {startError ? <div className="mb-2"><ErrorNotice message={startError} /></div> : null}
        <Composer onSend={handleSend} disabled={busy} autoFocus />
        <p className="mt-2 text-center text-xs text-muted">JobPilot can make mistakes. Check details on the posting before applying.</p>
      </div>
    </div>
  );
}
