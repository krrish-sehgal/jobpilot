"use client";

import { useState, type DragEvent } from "react";
import { CheckCircle2, FileUp, Loader2, XCircle } from "lucide-react";
import type { UploadState } from "@/hooks/useResumeUpload";
import { cn } from "@/lib/cn";
import { RESUME_ACCEPT } from "@/lib/resumeFile";

/**
 * Drag-and-drop target built on a real <input type="file"> inside a <label>,
 * so click, keyboard (Tab + Enter/Space) and screen readers all work without
 * custom role/tabindex code. Drag events only add the drop shortcut.
 */
export function UploadDropzone({ state, onFile, onReset }: { state: UploadState; onFile: (f: File) => void; onReset: () => void }) {
  const [dragging, setDragging] = useState(false);
  const busy = state.phase === "uploading" || state.phase === "parsing";

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file && !busy) onFile(file);
  };

  return (
    <div>
      <label
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={cn(
          "relative flex cursor-pointer flex-col items-center gap-2 rounded-xl border-2 border-dashed px-6 py-10 text-center transition-colors",
          "has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-brand has-[:focus-visible]:ring-offset-2 has-[:focus-visible]:ring-offset-paper",
          dragging ? "border-brand bg-brand/5" : "border-line bg-surface hover:border-brand/60",
          busy && "pointer-events-none opacity-70",
        )}
      >
        <input
          type="file"
          accept={RESUME_ACCEPT}
          className="sr-only"
          disabled={busy}
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) onFile(f);
            e.target.value = ""; // allow re-selecting the same file after an error
          }}
        />
        <FileUp className="h-8 w-8 text-brand" aria-hidden />
        <span className="font-medium">Drop your resume here, or click to browse</span>
        <span className="text-sm text-muted">PDF or DOCX, up to 5 MB</span>
      </label>

      <div aria-live="polite" className="mt-3 min-h-6 text-sm">
        {state.phase === "uploading" ? (
          <div>
            <p className="mb-1.5 flex items-center gap-2"><Loader2 className="h-4 w-4 animate-spin" aria-hidden /> Uploading {state.fileName}</p>
            <div className="h-1.5 overflow-hidden rounded-full bg-sunken" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(state.progress * 100)} aria-label="Upload progress">
              <div className="h-full bg-brand transition-[width]" style={{ width: `${state.progress * 100}%` }} />
            </div>
          </div>
        ) : state.phase === "parsing" ? (
          <p className="flex items-center gap-2"><Loader2 className="h-4 w-4 animate-spin" aria-hidden /> Reading {state.fileName} and extracting sections&hellip;</p>
        ) : state.phase === "ready" ? (
          <p className="flex items-center gap-2 text-good"><CheckCircle2 className="h-4 w-4" aria-hidden /> {state.fileName} is ready.</p>
        ) : state.phase === "failed" ? (
          <p role="alert" className="flex items-start gap-2 text-bad">
            <XCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
            <span className="flex-1">{state.message}</span>
            <button type="button" onClick={onReset} className="underline">Dismiss</button>
          </p>
        ) : null}
      </div>
    </div>
  );
}
