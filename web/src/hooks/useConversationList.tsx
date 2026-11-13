"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api } from "@/lib/api";
import type { ConversationSummary } from "@/lib/api/types";

interface ConversationListValue {
  conversations: ConversationSummary[];
  loading: boolean;
  error: boolean;
  refresh: () => Promise<void>;
  /** Insert or update one row locally so the sidebar reflects a new/renamed chat instantly. */
  upsert: (c: ConversationSummary) => void;
}

const Ctx = createContext<ConversationListValue | null>(null);

/**
 * The sidebar's list and the chat page both need to know about conversations
 * (a new chat appears in the list; a reply moves it to the top), so the list
 * lives in a context mounted by the /app layout rather than in either one.
 */
export function ConversationListProvider({ children }: { children: ReactNode }) {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setConversations(await api.listConversations());
      setError(false);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const upsert = useCallback((c: ConversationSummary) => {
    setConversations((prev) => [c, ...prev.filter((p) => p.id !== c.id)]);
  }, []);

  const value = useMemo(() => ({ conversations, loading, error, refresh, upsert }), [conversations, loading, error, refresh, upsert]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useConversationList(): ConversationListValue {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useConversationList must be used inside <ConversationListProvider>");
  return ctx;
}
