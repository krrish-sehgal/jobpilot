import type { Metadata } from "next";
import { JobDetailView } from "@/components/jobs/JobDetailView";

export const metadata: Metadata = { title: "Job details" };

export default function JobPage({ params }: { params: { jobId: string } }) {
  return <JobDetailView jobId={params.jobId} />;
}
