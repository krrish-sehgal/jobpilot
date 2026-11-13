"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState, type FormEvent } from "react";
import { api } from "@/lib/api";
import { describeError } from "@/lib/api/errors";
import type { JobDetail } from "@/lib/api/types";
import { useResumes } from "@/hooks/useResumes";
import { buttonClasses, Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { Skeleton } from "@/components/ui/Spinner";
import { cn } from "@/lib/cn";

type Source = "job" | "paste";
const MIN_JD_CHARS = 80;

/** /app/tailor/new: choose a resume and a target (a known job via ?jobId=, or a pasted description). */
export function TailorNewForm() {
  const router = useRouter();
  const jobId = useSearchParams().get("jobId");
  const { resumes, error: resumesError } = useResumes();

  const [source, setSource] = useState<Source>(jobId ? "job" : "paste");
  const [job, setJob] = useState<JobDetail | null>(null);
  const [jobError, setJobError] = useState<string | null>(null);
  const [resumeId, setResumeId] = useState("");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!jobId) return;
    let cancelled = false;
    api.getJob(jobId).then((j) => !cancelled && setJob(j)).catch((e) => !cancelled && setJobError(describeError(e)));
    return () => { cancelled = true; };
  }, [jobId]);

  const ready = useMemo(() => resumes?.filter((r) => r.status === "ready") ?? [], [resumes]);
  useEffect(() => {
    if (!resumeId && ready.length) setResumeId((ready.find((r) => r.is_primary) ?? ready[0]!).id);
  }, [ready, resumeId]);

  const canSubmit = Boolean(resumeId) && (source === "job" ? Boolean(job) : text.trim().length >= MIN_JD_CHARS);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    setBusy(true);
    setError(null);
    try {
      const input = source === "job" && jobId ? { resume_id: resumeId, job_id: jobId } : { resume_id: resumeId, job_description_text: text.trim() };
      const { tailoringId } = await api.createTailoring(input);
      router.push(`/app/tailor/${tailoringId}`);
    } catch (err) {
      setError(describeError(err));
      setBusy(false);
    }
  }

  if (resumesError) return <div className="mx-auto max-w-2xl p-6"><ErrorNotice message={resumesError} /></div>;
  if (!resumes) return <div className="mx-auto max-w-2xl space-y-3 p-6"><Skeleton className="h-10" /><Skeleton className="h-48" /></div>;
  if (ready.length === 0) {
    return (
      <div className="p-6">
        <EmptyState title="Upload a resume first" action={<Link href="/app/resume" className={buttonClasses("primary", "md")}>Go to Resume</Link>}>
          Tailoring needs a parsed resume to work from.
        </EmptyState>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-8">
      <h1 className="font-display text-3xl">Tailor your resume</h1>
      <p className="mt-1 text-muted">Pick a resume and a target role. You&apos;ll review every suggested edit before anything changes.</p>

      <Card className="mt-6 p-6">
        <form onSubmit={submit} className="space-y-6">
          <div>
            <label htmlFor="resume" className="mb-1.5 block text-sm font-medium">Resume</label>
            <select id="resume" value={resumeId} onChange={(e) => setResumeId(e.target.value)} className="h-11 w-full rounded-lg border border-line bg-paper px-3">
              {ready.map((r) => <option key={r.id} value={r.id}>{r.file_name}{r.is_primary ? " (primary)" : ""}</option>)}
            </select>
          </div>

          <fieldset>
            <legend className="mb-1.5 text-sm font-medium">Target</legend>
            <div className="mb-3 inline-flex rounded-lg border border-line p-0.5">
              {([["job", "Job from JobPilot"], ["paste", "Paste a description"]] as const).map(([value, label]) => (
                <label key={value} className={cn("cursor-pointer rounded-md px-3 py-1.5 text-sm has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-brand", source === value && "bg-sunken font-medium", value === "job" && !jobId && "opacity-50")}>
                  <input type="radio" name="source" value={value} checked={source === value} disabled={value === "job" && !jobId} onChange={() => setSource(value)} className="sr-only" />
                  {label}
                </label>
              ))}
            </div>

            {source === "job" ? (
              jobError ? <ErrorNotice message={jobError} /> : job ? (
                <div className="rounded-lg border border-line bg-paper p-4">
                  <p className="font-medium">{job.title}</p>
                  <p className="text-sm text-muted">{job.company} &middot; {job.location_text ?? "Location unspecified"}</p>
                </div>
              ) : <Skeleton className="h-16" />
            ) : (
              <>
                <label htmlFor="jd" className="sr-only">Job description</label>
                <textarea id="jd" rows={10} value={text} onChange={(e) => setText(e.target.value)} placeholder="Paste the full job description here&hellip;" className="w-full rounded-lg border border-line bg-paper p-3 text-sm" />
                <p className="mt-1 text-xs text-muted">{text.trim().length < MIN_JD_CHARS ? `At least ${MIN_JD_CHARS} characters, so there is enough to match against.` : "Looks good."}</p>
              </>
            )}
          </fieldset>

          {error ? <ErrorNotice message={error} /> : null}
          <Button type="submit" size="lg" className="w-full" loading={busy} disabled={!canSubmit}>Start tailoring</Button>
        </form>
      </Card>
    </div>
  );
}
