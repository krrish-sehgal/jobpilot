import type { Metadata } from "next";
import { TailoringView } from "@/components/tailor/TailoringView";

export const metadata: Metadata = { title: "Tailored resume" };

export default function TailoringPage({ params }: { params: { tailoringId: string } }) {
  // key: a different tailoring must start with fresh state, not the previous one's.
  return <TailoringView key={params.tailoringId} tailoringId={params.tailoringId} />;
}
