"use client";

import { api } from "@/lib/api";
import { usePolling } from "@/hooks/usePolling";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { Skeleton, Spinner } from "@/components/ui/Spinner";
import { ResumeSectionsView } from "./ResumeSections";

/** Fetches one resume and keeps polling while it is still `parsing`. Mount with a `key` per resume id. */
export function ResumeViewer({ resumeId }: { resumeId: string }) {
  const { data: resume, error, retry } = usePolling(() => api.getResume(resumeId), {
    intervalMs: 1200,
    isDone: (r) => r.status !== "parsing",
  });

  if (error) return <ErrorNotice message={error} onRetry={retry} />;
  if (!resume) return <div className="space-y-3"><Skeleton className="h-8 w-1/2" /><Skeleton className="h-40" /></div>;
  if (resume.status === "parsing") return <Spinner label="Parsing your resume" />;
  if (resume.status === "failed" || !resume.sections) {
    return <ErrorNotice message={resume.failure_reason ?? "We couldn't parse this resume. Try uploading a text-based PDF or a DOCX."} />;
  }
  return <ResumeSectionsView sections={resume.sections} />;
}
