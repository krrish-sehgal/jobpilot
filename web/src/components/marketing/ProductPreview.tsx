import { Check } from "lucide-react";
import { ScoreRing } from "@/components/ui/ScoreRing";
import { Badge } from "@/components/ui/Badge";

/** A static, hand-built picture of the product, so the hero shows the real thing instead of stock art. */
export function ProductPreview() {
  return (
    <div className="relative" aria-hidden>
      <div className="absolute -inset-4 -z-10 rotate-2 rounded-3xl bg-brand/10" />
      <div className="rounded-2xl border border-line bg-surface p-4 shadow-card">
        <div className="mb-3 flex items-center gap-1.5">
          {[0, 1, 2].map((i) => <span key={i} className="h-2.5 w-2.5 rounded-full bg-line" />)}
          <span className="ml-2 font-mono text-xs text-muted">jobpilot / chat</span>
        </div>
        <div className="ml-auto w-fit max-w-[80%] rounded-2xl rounded-br-sm bg-brand px-4 py-2 text-sm text-brand-ink">Show me remote backend roles</div>
        <div className="mt-3 space-y-2 text-sm">
          <p className="flex items-center gap-2 text-muted"><Check className="h-4 w-4 text-good" /> Searching remote backend roles</p>
          <p className="flex items-center gap-2 text-muted"><Check className="h-4 w-4 text-good" /> Found 6 matching roles</p>
          <p>The strongest is <strong>Senior Backend Engineer</strong> at <strong>Lumenfold</strong>.</p>
        </div>
        <div className="mt-3 flex items-start gap-3 rounded-xl border border-line bg-paper p-3">
          <ScoreRing value={91} />
          <div className="min-w-0 flex-1">
            <p className="font-medium">Senior Backend Engineer, Ledger</p>
            <p className="text-xs text-muted">Lumenfold - Remote (EU / UK)</p>
            <div className="mt-2 flex flex-wrap gap-1.5">
              <Badge tone="brand">Python + PostgreSQL</Badge>
              <Badge tone="brand">Fully remote</Badge>
            </div>
          </div>
        </div>
        <div className="mt-3 rounded-xl border border-dashed border-signal/50 bg-signal/5 p-3 text-xs">
          <span className="font-mono text-muted">resume score</span>{" "}
          <span className="font-semibold">58</span> <span className="text-muted">to</span> <span className="font-semibold text-good">86</span>
        </div>
      </div>
    </div>
  );
}
