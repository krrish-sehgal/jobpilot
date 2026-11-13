"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "@/lib/api";
import { describeError } from "@/lib/api/errors";
import type { Resume, Tailoring } from "@/lib/api/types";
import { applySuggestions } from "@/lib/resumeApply";
import { usePolling } from "./usePolling";

type Decision = "accepted" | "rejected";

/**
 * Everything the tailoring screen needs:
 *  1. polls `GET /tailorings/{id}` until it leaves `running`
 *  2. loads the source resume once it's ready (for the live preview)
 *  3. records accept / reject decisions optimistically, then reconciles with the server's response
 *  4. derives the preview resume from the accepted suggestions
 */
export function useTailoring(tailoringId: string) {
  const poll = usePolling(() => api.getTailoring(tailoringId), {
    intervalMs: 1200,
    isDone: (t) => t.status !== "running",
  });
  const [tailoring, setTailoring] = useState<Tailoring | null>(null);
  const [resume, setResume] = useState<Resume | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [resumeFailed, setResumeFailed] = useState(false);

  useEffect(() => {
    if (poll.data) setTailoring(poll.data);
  }, [poll.data]);

  const resumeId = tailoring?.status === "ready" ? tailoring.resume_id : null;
  useEffect(() => {
    if (!resumeId) return;
    let cancelled = false;
    setResumeFailed(false);
    api
      .getResume(resumeId)
      .then((r) => !cancelled && setResume(r))
      .catch(() => !cancelled && setResumeFailed(true)); // surfaced as "Preview unavailable"
    return () => { cancelled = true; };
  }, [resumeId]);

  // Requests are chained so two quick clicks can't have their responses arrive out of order.
  const queue = useRef<Promise<unknown>>(Promise.resolve());

  const decide = useCallback((ids: string[], decision: Decision) => {
    if (ids.length === 0) return;
    setActionError(null);
    setTailoring((cur) => cur && { ...cur, suggestions: cur.suggestions.map((s) => (ids.includes(s.id) ? { ...s, decision } : s)) });
    queue.current = queue.current.then(async () => {
      try {
        const next = await api.submitDecisions(tailoringId, decision === "accepted" ? ids : [], decision === "rejected" ? ids : []);
        setTailoring(next);
      } catch (e) {
        setActionError(describeError(e));
        // Don't guess the old state back: earlier queued decisions may have succeeded, so ask the server.
        try {
          setTailoring(await api.getTailoring(tailoringId));
        } catch {
          /* keep the optimistic state; the error notice above tells the user something is off */
        }
      }
    });
  }, [tailoringId]);

  /** Resolves once every queued decision request has finished (success or failure). Call before exporting. */
  const settled = useCallback((): Promise<unknown> => queue.current, []);

  const pendingIds = useMemo(() => tailoring?.suggestions.filter((s) => s.decision === "pending").map((s) => s.id) ?? [], [tailoring]);

  const preview = useMemo(
    () => (tailoring && resume?.sections ? applySuggestions(resume.sections, tailoring.suggestions) : null),
    [tailoring, resume],
  );

  // Sections are null when the resume isn't "ready"; a failed load is the same user-facing problem.
  const previewUnavailable = resumeFailed || (resume !== null && resume.sections === null);

  return {
    tailoring,
    preview,
    previewUnavailable,
    settled,
    error: poll.error,
    retry: poll.retry,
    actionError,
    accept: (id: string) => decide([id], "accepted"),
    reject: (id: string) => decide([id], "rejected"),
    acceptAll: () => decide(pendingIds, "accepted"),
    pendingCount: pendingIds.length,
  };
}
