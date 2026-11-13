"use client";

import Link from "next/link";
import { useState } from "react";
import { ArrowLeft, CheckCheck, Columns2, Rows3 } from "lucide-react";
import { useTailoring } from "@/hooks/useTailoring";
import { ResumeSectionsView } from "@/components/resume/ResumeSections";
import { Button } from "@/components/ui/Button";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { Skeleton, Spinner } from "@/components/ui/Spinner";
import { ExportButtons } from "./ExportButtons";
import { KeywordCoverage } from "./KeywordCoverage";
import { ScoreMeter } from "./ScoreMeter";
import { SuggestionCard } from "./SuggestionCard";

/** /app/tailor/[id]: waits for the run, then lets you review edits, preview the result and export. */
export function TailoringView({ tailoringId }: { tailoringId: string }) {
  const t = useTailoring(tailoringId);
  const [mode, setMode] = useState<"inline" | "split">("inline");
  const { tailoring } = t;

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <Link href="/app/chat" className="mb-6 inline-flex items-center gap-1.5 text-sm text-muted hover:text-ink">
        <ArrowLeft className="h-4 w-4" aria-hidden /> Back to chat
      </Link>

      {t.error ? <ErrorNotice message={t.error} onRetry={t.retry} /> : !tailoring ? (
        <div className="space-y-4"><Skeleton className="h-10 w-1/2" /><Skeleton className="h-40" /></div>
      ) : tailoring.status === "running" ? (
        <div className="flex flex-col items-center gap-3 rounded-xl border border-line bg-surface py-20 text-center" aria-live="polite">
          <Spinner label="Tailoring your resume" />
          <p className="max-w-sm text-sm text-muted">Comparing your resume with <strong>{tailoring.job_title}</strong> and drafting edits. This usually takes a few seconds.</p>
        </div>
      ) : tailoring.status === "failed" ? (
        <ErrorNotice message="Tailoring failed. Your resume was not changed. Start a new tailoring to try again." />
      ) : (
        <>
          <header className="mb-6">
            <p className="font-mono text-xs uppercase tracking-widest text-signal">Tailored for</p>
            <h1 className="font-display text-3xl">{tailoring.job_title}{tailoring.company ? ` at ${tailoring.company}` : ""}</h1>
          </header>

          <div className="grid gap-4 md:grid-cols-2">
            <ScoreMeter before={tailoring.score_before} after={tailoring.score_after} />
            <KeywordCoverage keywords={tailoring.keywords} />
          </div>

          <div className="mt-8 grid gap-8 lg:grid-cols-[1fr_26rem]">
            <section aria-labelledby="sug-h">
              <div className="mb-3 flex flex-wrap items-center gap-2">
                <h2 id="sug-h" className="mr-auto font-display text-xl">Suggested edits ({tailoring.suggestions.length})</h2>
                <div className="inline-flex rounded-lg border border-line p-0.5" role="group" aria-label="Diff layout">
                  <button type="button" aria-pressed={mode === "inline"} onClick={() => setMode("inline")} className={`rounded-md p-1.5 ${mode === "inline" ? "bg-sunken" : ""}`} aria-label="Inline diff"><Rows3 className="h-4 w-4" aria-hidden /></button>
                  <button type="button" aria-pressed={mode === "split"} onClick={() => setMode("split")} className={`rounded-md p-1.5 ${mode === "split" ? "bg-sunken" : ""}`} aria-label="Side-by-side diff"><Columns2 className="h-4 w-4" aria-hidden /></button>
                </div>
                <Button size="sm" onClick={t.acceptAll} disabled={t.pendingCount === 0} icon={<CheckCheck className="h-4 w-4" aria-hidden />}>
                  Accept all{t.pendingCount ? ` (${t.pendingCount})` : ""}
                </Button>
              </div>
              {t.actionError ? <div className="mb-3"><ErrorNotice message={t.actionError} /></div> : null}
              <ul className="space-y-3">
                {tailoring.suggestions.map((s) => (
                  <SuggestionCard key={s.id} suggestion={s} mode={mode} onAccept={() => t.accept(s.id)} onReject={() => t.reject(s.id)} />
                ))}
              </ul>
            </section>

            <aside aria-labelledby="prev-h" className="space-y-4 lg:sticky lg:top-4 lg:self-start">
              <div className="rounded-xl border border-line bg-surface p-5">
                <h2 id="prev-h" className="mb-4 font-display text-xl">Live preview</h2>
                {t.preview ? (
                  <ResumeSectionsView sections={t.preview.sections} order={t.preview.order} changed={t.preview.changed} />
                ) : t.previewUnavailable ? (
                  <p className="text-sm text-muted">Preview unavailable. You can still review the edits and export.</p>
                ) : (
                  <Skeleton className="h-64" />
                )}
                <p className="mt-4 text-xs text-muted">Highlighted text comes from edits you accepted.</p>
              </div>
              <ExportButtons tailoringId={tailoring.id} settled={t.settled} />
            </aside>
          </div>
        </>
      )}
    </div>
  );
}
