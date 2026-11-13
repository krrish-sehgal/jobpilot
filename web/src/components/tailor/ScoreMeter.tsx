import { ArrowRight } from "lucide-react";

function Bar({ label, value, tone }: { label: string; value: number; tone: string }) {
  return (
    <div>
      <div className="mb-1 flex justify-between text-sm"><span className="text-muted">{label}</span><span className="font-semibold tabular-nums">{value}</span></div>
      <div className="h-2.5 overflow-hidden rounded-full bg-sunken" role="meter" aria-label={label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={value}>
        <div className={`h-full rounded-full transition-[width] duration-700 ${tone}`} style={{ width: `${value}%` }} />
      </div>
    </div>
  );
}

/** Match score before and after. `after` is the projection with every non-rejected edit applied (pending ones included). */
export function ScoreMeter({ before, after }: { before: number; after: number }) {
  const delta = after - before;
  return (
    <section aria-label="Match score" className="rounded-xl border border-line bg-surface p-5">
      <div className="flex items-baseline gap-3">
        <span className="font-display text-4xl tabular-nums">{before}</span>
        <ArrowRight className="h-5 w-5 text-muted" aria-hidden />
        <span className="font-display text-4xl tabular-nums text-good">{after}</span>
        <span className="ml-auto text-sm text-muted">{delta >= 0 ? "+" : ""}{delta} points</span>
      </div>
      <div className="mt-4 space-y-3">
        <Bar label="Original resume" value={before} tone="bg-muted" />
        <Bar label="If you keep the remaining edits" value={after} tone="bg-good" />
      </div>
    </section>
  );
}
