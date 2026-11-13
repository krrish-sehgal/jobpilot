"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Bookmark } from "lucide-react";
import { api } from "@/lib/api";
import { describeError } from "@/lib/api/errors";
import type { JobCard } from "@/lib/api/types";
import { buttonClasses } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { Skeleton } from "@/components/ui/Spinner";
import { JobCardGrid } from "./JobCardList";

export function SavedJobs() {
  const [jobs, setJobs] = useState<JobCard[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    api.listSavedJobs().then((j) => !cancelled && setJobs(j)).catch((e) => !cancelled && setError(describeError(e)));
    return () => { cancelled = true; };
  }, [nonce]);

  // Unsaving from this page removes the card straight away (the API call already happened in SaveButton).
  const onSaveChange = (jobId: string, saved: boolean) => {
    if (!saved) setJobs((prev) => prev?.filter((j) => j.job_id !== jobId) ?? prev);
  };

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <h1 className="font-display text-3xl">Saved jobs</h1>
      <p className="mt-1 text-muted">Roles you bookmarked from chat or a posting.</p>
      <div className="mt-6">
        {error ? <ErrorNotice message={error} onRetry={() => setNonce((n) => n + 1)} /> : !jobs ? (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-48" />)}</div>
        ) : jobs.length === 0 ? (
          <EmptyState icon={<Bookmark className="h-8 w-8" aria-hidden />} title="Nothing saved yet" action={<Link href="/app/chat" className={buttonClasses("primary", "md")}>Find some roles</Link>}>
            Tap Save on any job card and it will show up here.
          </EmptyState>
        ) : (
          <JobCardGrid jobs={jobs} onSaveChange={onSaveChange} />
        )}
      </div>
    </div>
  );
}
