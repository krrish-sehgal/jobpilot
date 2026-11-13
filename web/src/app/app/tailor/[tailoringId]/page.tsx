import type { Metadata } from "next";
import { TailoringView } from "@/components/tailor/TailoringView";

export const metadata: Metadata = { title: "Tailored resume" };

export default function TailoringPage({ params }: { params: { tailoringId: string } }) {
  return <TailoringView tailoringId={params.tailoringId} />;
}
