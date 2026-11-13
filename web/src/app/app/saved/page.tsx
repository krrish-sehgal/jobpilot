import type { Metadata } from "next";
import { SavedJobs } from "@/components/jobs/SavedJobs";

export const metadata: Metadata = { title: "Saved jobs" };

export default function SavedPage() {
  return <SavedJobs />;
}
