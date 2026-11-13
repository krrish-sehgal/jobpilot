import type { JobCard as JobCardData } from "@/lib/api/types";
import { JobCard } from "./JobCard";

/** Horizontal snap-scrolling carousel, used under chat replies where vertical space is precious. */
export function JobCardCarousel({ jobs }: { jobs: JobCardData[] }) {
  return (
    <ul
      className="scroll-thin -mx-1 flex snap-x snap-mandatory gap-3 overflow-x-auto px-1 pb-3"
      aria-label={`${jobs.length} matching jobs`}
      // Makes the carousel keyboard-scrollable for people who can't see its overflow.
      tabIndex={0}
    >
      {jobs.map((job) => (
        <li key={job.job_id} className="w-[19rem] shrink-0 snap-start sm:w-80">
          <JobCard job={job} />
        </li>
      ))}
    </ul>
  );
}

/** Responsive grid for full pages (saved jobs). */
export function JobCardGrid({ jobs, onSaveChange }: { jobs: JobCardData[]; onSaveChange?: (jobId: string, saved: boolean) => void }) {
  return (
    <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {jobs.map((job) => (
        <li key={job.job_id}>
          <JobCard job={job} onSaveChange={(s) => onSaveChange?.(job.job_id, s)} />
        </li>
      ))}
    </ul>
  );
}
