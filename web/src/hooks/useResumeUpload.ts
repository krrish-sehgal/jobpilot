"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { describeError, isApiError } from "@/lib/api/errors";
import { validateResumeFile } from "@/lib/resumeFile";
import { usePolling } from "./usePolling";

export type UploadState =
  | { phase: "idle" }
  | { phase: "uploading"; fileName: string; progress: number }
  | { phase: "parsing"; fileName: string; resumeId: string }
  | { phase: "ready"; fileName: string; resumeId: string }
  | { phase: "failed"; fileName: string; message: string };

/**
 * validate -> upload (with progress) -> poll until parsing finishes.
 * `onFinished` fires when the resume becomes ready so the page can refresh its list.
 */
export function useResumeUpload(onFinished: (resumeId: string) => void) {
  const [state, setState] = useState<UploadState>({ phase: "idle" });
  const abort = useRef<AbortController | null>(null);
  const finishedRef = useRef(onFinished);
  finishedRef.current = onFinished;

  const parsingId = state.phase === "parsing" ? state.resumeId : null;
  const poll = usePolling(() => api.getResume(parsingId!), {
    intervalMs: 1000,
    enabled: parsingId !== null,
    isDone: (r) => r.status !== "parsing",
  });

  useEffect(() => {
    if (state.phase !== "parsing") return;
    const r = poll.data;
    if (poll.error) {
      setState({ phase: "failed", fileName: state.fileName, message: poll.error });
      return;
    }
    if (!r || r.id !== state.resumeId) return; // stale result from a previous upload
    if (r.status === "ready") {
      setState({ phase: "ready", fileName: state.fileName, resumeId: r.id });
      finishedRef.current(r.id);
    } else if (r.status === "failed") {
      setState({ phase: "failed", fileName: state.fileName, message: r.failure_reason ?? "We couldn't read that file." });
      finishedRef.current(r.id); // it still appears in the list, marked failed
    }
  }, [poll.data, poll.error, state]);

  useEffect(() => () => abort.current?.abort(), []);

  const upload = useCallback(async (file: File) => {
    const invalid = validateResumeFile(file);
    if (invalid) {
      setState({ phase: "failed", fileName: file.name, message: describeError(invalid) });
      return;
    }

    abort.current?.abort();
    const controller = new AbortController();
    abort.current = controller;
    setState({ phase: "uploading", fileName: file.name, progress: 0 });
    try {
      const { resumeId } = await api.uploadResume(file, (progress) => setState({ phase: "uploading", fileName: file.name, progress }), controller.signal);
      setState({ phase: "parsing", fileName: file.name, resumeId });
    } catch (e) {
      if (controller.signal.aborted) return;
      setState({ phase: "failed", fileName: file.name, message: isApiError(e) ? describeError(e) : "Upload failed. Please try again." });
    }
  }, []);

  const reset = useCallback(() => setState({ phase: "idle" }), []);
  return { state, upload, reset };
}
