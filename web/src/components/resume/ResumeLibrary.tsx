"use client";

import { useEffect, useState } from "react";
import { FileText } from "lucide-react";
import { useResumeUpload } from "@/hooks/useResumeUpload";
import { useResumes } from "@/hooks/useResumes";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { Skeleton } from "@/components/ui/Spinner";
import { ResumeList } from "./ResumeList";
import { ResumeViewer } from "./ResumeViewer";
import { UploadDropzone } from "./UploadDropzone";

/** The /app/resume screen: upload on the left, parsed view of the selected resume on the right. */
export function ResumeLibrary() {
  const { resumes, error, refresh, makePrimary } = useResumes();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const upload = useResumeUpload((id) => {
    setSelectedId(id);
    void refresh();
  });

  // Default to the primary resume (or the newest) once the list loads.
  useEffect(() => {
    if (selectedId || !resumes?.length) return;
    setSelectedId((resumes.find((r) => r.is_primary) ?? resumes[0]!).id);
  }, [resumes, selectedId]);

  // While an upload is parsing it already exists server-side; show it in the list.
  useEffect(() => {
    if (upload.state.phase === "parsing") void refresh();
  }, [upload.state.phase, refresh]);

  return (
    <div className="mx-auto grid max-w-6xl gap-8 px-4 py-8 lg:grid-cols-[22rem_1fr]">
      <div className="space-y-6">
        <div>
          <h1 className="font-display text-3xl">Resume</h1>
          <p className="mt-1 text-sm text-muted">Your primary resume is what the agent reads when it matches and tailors.</p>
        </div>
        <UploadDropzone state={upload.state} onFile={upload.upload} onReset={upload.reset} />
        {error ? <ErrorNotice message={error} onRetry={refresh} /> : !resumes ? <Skeleton className="h-16" /> : (
          <ResumeList resumes={resumes} selectedId={selectedId} onSelect={setSelectedId} onMakePrimary={makePrimary} />
        )}
      </div>

      <section aria-label="Parsed resume" className="min-w-0 rounded-xl border border-line bg-surface p-6">
        {selectedId ? <ResumeViewer key={selectedId} resumeId={selectedId} /> : (
          <EmptyState icon={<FileText className="h-8 w-8" aria-hidden />} title="No resume yet">Upload a PDF or DOCX and we&apos;ll break it into sections you can review.</EmptyState>
        )}
      </section>
    </div>
  );
}
