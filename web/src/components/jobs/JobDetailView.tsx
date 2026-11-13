"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowLeft, ExternalLink, MapPin, Wand2 } from "lucide-react";
import { api } from "@/lib/api";
import { describeError } from "@/lib/api/errors";
import type { JobDetail } from "@/lib/api/types";
import { categoryLabel, employmentLabel, seniorityLabel, tierLabel } from "@/lib/labels";
import { timeAgo } from "@/lib/format";
import { Markdown } from "@/lib/markdown";
import { Badge } from "@/components/ui/Badge";
import { buttonClasses } from "@/components/ui/Button";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { ScoreRing } from "@/components/ui/ScoreRing";
import { Skeleton } from "@/components/ui/Spinner";
import { SaveButton } from "./SaveButton";

/** Full posting page. The description comes from the backend as markdown-lite text. */
export function JobDetailView({ jobId }: { jobId: string }) {
  const [job, setJob] = useState<JobDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    api.getJob(jobId).then((j) => !cancelled && setJob(j)).catch((e) => !cancelled && setError(describeError(e)));
    return () => { cancelled = true; };
  }, [jobId, nonce]);

  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      <Link href="/app/chat" className="mb-6 inline-flex items-center gap-1.5 text-sm text-muted hover:text-ink">
        <ArrowLeft className="h-4 w-4" aria-hidden /> Back to chat
      </Link>

      {error ? <ErrorNotice message={error} onRetry={() => setNonce((n) => n + 1)} /> : !job ? (
        <div className="space-y-4"><Skeleton className="h-10 w-2/3" /><Skeleton className="h-5 w-1/3" /><Skeleton className="h-64" /></div>
      ) : (
        <article>
          <header className="flex items-start gap-4">
            <div className="min-w-0 flex-1">
              <h1 className="font-display text-3xl leading-tight sm:text-4xl">{job.title}</h1>
              <p className="mt-1 text-lg text-muted">{job.company}</p>
              <p className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted">
                <span className="inline-flex items-center gap-1"><MapPin className="h-4 w-4" aria-hidden />{job.location_text ?? tierLabel[job.location_tier]}</span>
                <span>{tierLabel[job.location_tier]}</span>
                <span>{seniorityLabel[job.seniority_band]}</span>
                <span>{employmentLabel[job.employment_type]}</span>
                {job.posted_at ? <span>Posted {timeAgo(job.posted_at)}</span> : null}
              </p>
            </div>
            <ScoreRing value={job.match_score} size={64} />
          </header>

          <div className="mt-6 flex flex-wrap gap-2">
            <Link href={`/app/tailor/new?jobId=${job.job_id}`} className={buttonClasses("primary", "md")}>
              <Wand2 className="h-4 w-4" aria-hidden /> Tailor my resume for this job
            </Link>
            <a href={job.apply_url} target="_blank" rel="noopener noreferrer" className={buttonClasses("secondary", "md")}>
              Apply <ExternalLink className="h-4 w-4" aria-hidden />
              <span className="sr-only">(opens in a new tab)</span>
            </a>
            <SaveButton jobId={job.job_id} initialSaved={job.is_saved} />
          </div>

          <dl className="mt-8 grid gap-4 rounded-xl border border-line bg-surface p-5 text-sm sm:grid-cols-3">
            <div><dt className="text-muted">Compensation</dt><dd className="mt-0.5 font-medium">{job.compensation_text ?? "Not listed"}</dd></div>
            <div><dt className="text-muted">Experience</dt><dd className="mt-0.5 font-medium">{job.min_years_experience === 0 ? "No minimum" : `${job.min_years_experience}+ years`}</dd></div>
            <div><dt className="text-muted">Category</dt><dd className="mt-0.5 font-medium">{categoryLabel[job.role_category]}</dd></div>
          </dl>

          {job.match_reasons.length > 0 ? (
            <section className="mt-8" aria-labelledby="why">
              <h2 id="why" className="font-display text-xl">Why it matches</h2>
              <ul className="mt-3 flex flex-wrap gap-2">{job.match_reasons.map((r) => <li key={r}><Badge tone="brand">{r}</Badge></li>)}</ul>
            </section>
          ) : null}

          <section className="mt-8" aria-labelledby="skills">
            <h2 id="skills" className="font-display text-xl">Skills</h2>
            <ul className="mt-3 flex flex-wrap gap-2">{job.skills.map((s) => <li key={s}><Badge>{s}</Badge></li>)}</ul>
          </section>

          <section className="mt-8" aria-labelledby="about">
            <h2 id="about" className="mb-3 font-display text-xl">About the role</h2>
            <div className="max-w-none rounded-xl border border-line bg-surface p-6"><Markdown source={job.description} /></div>
          </section>
        </article>
      )}
    </div>
  );
}
