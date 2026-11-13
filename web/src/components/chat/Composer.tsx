"use client";

import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { SendHorizonal } from "lucide-react";
import { Button } from "@/components/ui/Button";

/**
 * Message box. Enter sends, Shift+Enter inserts a newline. While a turn is
 * streaming the send button is disabled (one turn at a time) but you can still
 * type your next message. IME composition is respected so Enter confirming a
 * candidate doesn't send half a word.
 */
export function Composer({ onSend, disabled, autoFocus = false }: { onSend: (text: string) => void; disabled: boolean; autoFocus?: boolean }) {
  const [value, setValue] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);

  // Grow with content up to a cap.
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 180)}px`;
  }, [value]);

  useEffect(() => {
    if (autoFocus) ref.current?.focus();
  }, [autoFocus]);

  function submit() {
    const text = value.trim();
    if (!text || disabled) return;
    onSend(text);
    setValue("");
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit();
    }
  }

  return (
    <form onSubmit={(e) => { e.preventDefault(); submit(); }} className="flex items-end gap-2 rounded-2xl border border-line bg-surface p-2 shadow-card focus-within:border-brand">
      <label htmlFor="composer" className="sr-only">Message JobPilot</label>
      <textarea
        id="composer"
        ref={ref}
        rows={1}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={onKeyDown}
        placeholder="Ask for roles, or say what you're looking for&hellip;"
        className="max-h-44 min-h-[2.5rem] flex-1 resize-none bg-transparent px-2 py-2 text-base outline-none placeholder:text-muted/70 focus-visible:ring-0"
      />
      <Button type="submit" size="md" disabled={disabled || !value.trim()} aria-label="Send message" icon={<SendHorizonal className="h-4 w-4" aria-hidden />}>
        <span className="hidden sm:inline">Send</span>
      </Button>
    </form>
  );
}
