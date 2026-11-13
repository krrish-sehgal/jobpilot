"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { describeError, isApiError } from "@/lib/api/errors";
import type { ChatMessage } from "@/lib/api/types";

/**
 * Loads one conversation's history and lets the chat append to it locally
 * (the optimistic user message, then the finished assistant reply) without
 * refetching. `skipLoad` is for a brand-new chat whose only message is the
 * one we are about to send, so there is nothing on the server to fetch yet.
 */
export function useConversation(conversationId: string | null, skipLoad = false) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(Boolean(conversationId) && !skipLoad);
  const [error, setError] = useState<string | null>(null);
  /** A 404 is permanent, so it is reported apart from `error` (which offers a retry). */
  const [notFound, setNotFound] = useState(false);
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    if (!conversationId || skipLoad) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    setNotFound(false);
    api
      .listMessages(conversationId)
      .then((m) => !cancelled && setMessages(m))
      .catch((e) => {
        if (cancelled) return;
        if (isApiError(e) && e.code === "not_found") setNotFound(true);
        else setError(describeError(e));
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
    // skipLoad is only read on first run for a given id.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conversationId, nonce]);

  /** Appends unless a message with this id is already there (keeps retries from duplicating the bubble). */
  const append = useCallback((msg: ChatMessage) => {
    setMessages((prev) => (prev.some((m) => m.id === msg.id) ? prev : [...prev, msg]));
  }, []);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  return { messages, loading, error, notFound, append, reload };
}
