import Link from "next/link";
import { MapPin, Wand2 } from "lucide-react";
import type { JobCard as JobCardData } from "@/lib/api/types";
import { seniorityLabel, tierLabel } from "@/lib/labels";
import { Badge } from "@/components/ui/Badge";
import { buttonClasses } from "@/components/ui/Button";
import { ScoreRing } from "@/components/ui/ScoreRing";
import { cn } from "@/lib/cn";
import { SaveButton } from "./SaveButton";

/** One job result: used in chat replies, the saved-jobs grid and anywhere else a posting is summarised. */
export function JobCard({ job, className, onSaveChange }: { job: JobCardData; className?: string; onSaveChange?: (saved: boolean) => void }) {
  return (
    <article className={cn("flex h-full flex-col gap-3 rounded-xl border border-line bg-surface p-4 shadow-card", className)} aria-label={`${job.title} at ${job.company}`}>
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <h3 className="font-display text-lg leading-snug">
            <Link href={`/app/jobs/${job.job_id}`} className="hover:text-brand hover:underline">{job.title}</Link>
          </h3>
          <p className="text-sm text-muted">{job.company}</p>
        </div>
        <ScoreRing value={job.match_score} />
      </div>

      <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted">
        <span className="inline-flex items-center gap-1"><MapPin className="h-3.5 w-3.5" aria-hidden />{job.location_text ?? tierLabel[job.location_tier]}</span>
        <span>{seniorityLabel[job.seniority_band]}</span>
        {job.compensation_text ? <span>{job.compensation_text}</span> : null}
      </p>

      {job.match_reasons.length > 0 ? (
        <ul className="flex flex-wrap gap-1.5" aria-label="Why this matches">
          {job.match_reasons.map((r) => <li key={r}><Badge tone="brand">{r}</Badge></li>)}
        </ul>
      ) : null}

      <div className="mt-auto flex flex-wrap items-center gap-2 pt-1">
        <SaveButton jobId={job.job_id} initialSaved={job.is_saved} onChange={onSaveChange} />
        <Link href={`/app/jobs/${job.job_id}`} className={buttonClasses("secondary", "sm")}>Details</Link>
        <Link href={`/app/tailor/new?jobId=${job.job_id}`} className={buttonClasses("ghost", "sm", "text-brand")}>
          <Wand2 className="h-3.5 w-3.5" aria-hidden /> Tailor my resume
        </Link>
      </div>
    </article>
  );
}
