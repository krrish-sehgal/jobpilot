import Link from "next/link";
import { ArrowRight, Wand2 } from "lucide-react";

/** Inline card shown when the agent kicks off a tailoring (`tailoring_started`). */
export function TailoringCard({ tailoringId }: { tailoringId: string }) {
  return (
    <Link
      href={`/app/tailor/${tailoringId}`}
      className="group flex items-center gap-3 rounded-xl border border-signal/40 bg-signal/5 p-4 hover:bg-signal/10"
    >
      <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-signal/15 text-signal"><Wand2 className="h-5 w-5" aria-hidden /></span>
      <span className="flex-1">
        <span className="block font-medium">Review tailored resume</span>
        <span className="block text-sm text-muted">Review the suggested edits and export when you are happy.</span>
      </span>
      <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" aria-hidden />
    </Link>
  );
}
