"use client";

import { useState } from "react";
import { Bookmark, BookmarkCheck } from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";

/**
 * Optimistic save toggle: flips immediately, calls the API, and rolls back if
 * the call fails. `onChange` lets the saved-jobs page drop an unsaved card.
 */
export function SaveButton({
  jobId,
  initialSaved,
  onChange,
}: {
  jobId: string;
  initialSaved: boolean;
  onChange?: (saved: boolean) => void;
}) {
  const [saved, setSaved] = useState(initialSaved);
  const [pending, setPending] = useState(false);
  const [failed, setFailed] = useState(false);

  async function toggle() {
    const next = !saved;
    setSaved(next);
    setPending(true);
    setFailed(false);
    try {
      await (next ? api.saveJob(jobId) : api.unsaveJob(jobId));
      onChange?.(next);
    } catch {
      setSaved(!next);
      setFailed(true);
    } finally {
      setPending(false);
    }
  }

  const Icon = saved ? BookmarkCheck : Bookmark;
  return (
    <button
      type="button"
      onClick={toggle}
      disabled={pending}
      aria-pressed={saved}
      className={cn(
        "inline-flex h-8 items-center gap-1.5 rounded-lg border px-2.5 text-sm font-medium transition-colors",
        saved ? "border-brand/40 bg-brand/10 text-brand" : "border-line bg-surface hover:bg-sunken",
        failed && "border-bad/50",
      )}
    >
      <Icon className="h-4 w-4" aria-hidden />
      <span>{failed ? "Retry" : saved ? "Saved" : "Save"}</span>
    </button>
  );
}
