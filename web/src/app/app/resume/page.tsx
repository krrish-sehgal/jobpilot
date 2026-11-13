import type { Metadata } from "next";
import { ResumeLibrary } from "@/components/resume/ResumeLibrary";

export const metadata: Metadata = { title: "Resume" };

export default function ResumePage() {
  return <ResumeLibrary />;
}
