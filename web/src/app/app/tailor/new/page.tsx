import { Suspense } from "react";
import type { Metadata } from "next";
import { TailorNewForm } from "@/components/tailor/TailorNewForm";

export const metadata: Metadata = { title: "Tailor resume" };

export default function NewTailoringPage() {
  // useSearchParams (for ?jobId=) requires a Suspense boundary.
  return (
    <Suspense fallback={null}>
      <TailorNewForm />
    </Suspense>
  );
}
