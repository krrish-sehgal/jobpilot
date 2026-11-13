"use client";

import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { ArrowDown } from "lucide-react";
import type { ChatMessage } from "@/lib/api/types";
import { MessageBubble } from "./MessageBubble";

const NEAR_BOTTOM_PX = 96;

/**
 * Scrollable thread with "sticky" auto-scroll: while you are near the bottom,
 * new content (tokens, cards) keeps you pinned there; once you scroll up to
 * read, we stop yanking you down and offer a "Jump to latest" button instead.
 * `followKey` changes whenever streamed content grows.
 */
export function MessageList({ messages, followKey, children }: { messages: ChatMessage[]; followKey: unknown; children?: ReactNode }) {
  const scroller = useRef<HTMLDivElement>(null);
  const pinned = useRef(true);
  const [showJump, setShowJump] = useState(false);

  const toBottom = useCallback((smooth = false) => {
    const el = scroller.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: smooth ? "smooth" : "auto" });
  }, []);

  const onScroll = () => {
    const el = scroller.current;
    if (!el) return;
    pinned.current = el.scrollHeight - el.scrollTop - el.clientHeight < NEAR_BOTTOM_PX;
    setShowJump(!pinned.current);
  };

  // Sending your own message always re-pins.
  const lastRole = messages[messages.length - 1]?.role;
  useEffect(() => {
    if (lastRole === "user") pinned.current = true;
  }, [lastRole, messages.length]);

  useEffect(() => {
    if (pinned.current) toBottom();
  }, [messages.length, followKey, toBottom]);

  return (
    <div className="relative min-h-0 flex-1">
      <div ref={scroller} onScroll={onScroll} className="scroll-thin h-full overflow-y-auto" role="log" aria-label="Conversation">
        <div className="mx-auto max-w-3xl space-y-6 px-4 py-6">
          {messages.map((m) => <MessageBubble key={m.id} message={m} />)}
          {children}
        </div>
      </div>
      {showJump ? (
        <button
          type="button"
          onClick={() => { pinned.current = true; setShowJump(false); toBottom(true); }}
          className="absolute bottom-3 left-1/2 flex -translate-x-1/2 items-center gap-1.5 rounded-full border border-line bg-surface px-3 py-1.5 text-sm shadow-card"
        >
          <ArrowDown className="h-3.5 w-3.5" aria-hidden /> Jump to latest
        </button>
      ) : null}
    </div>
  );
}
