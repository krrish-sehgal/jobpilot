import { diffWords } from "@/lib/diff";
import { cn } from "@/lib/cn";

/**
 * Renders a word diff. `inline` interleaves removals (struck through) and
 * additions (highlighted); `split` shows the old text and new text in two
 * columns, each marking only its own changes. Color is never the only signal:
 * removals are struck through and additions underlined.
 */
export function DiffText({ before, after, mode }: { before: string; after: string; mode: "inline" | "split" }) {
  const ops = diffWords(before, after);

  if (mode === "inline") {
    return (
      <p className="text-sm leading-relaxed">
        {ops.map((op, i) =>
          op.type === "equal" ? <span key={i}>{op.text}</span>
          : op.type === "delete" ? <del key={i} className="rounded bg-bad/15 text-bad decoration-bad/70">{op.text}</del>
          : <ins key={i} className="rounded bg-good/15 text-ink underline decoration-good/70 underline-offset-2">{op.text}</ins>,
        )}
      </p>
    );
  }

  const side = (keep: "delete" | "insert") => (
    <p className="text-sm leading-relaxed">
      {ops.filter((o) => o.type === "equal" || o.type === keep).map((op, i) => (
        <span key={i} className={cn(op.type === "delete" && "rounded bg-bad/15 line-through", op.type === "insert" && "rounded bg-good/15 underline decoration-good/70 underline-offset-2")}>{op.text}</span>
      ))}
    </p>
  );

  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <div><p className="mb-1 text-xs font-semibold uppercase tracking-wider text-muted">Before</p>{side("delete")}</div>
      <div><p className="mb-1 text-xs font-semibold uppercase tracking-wider text-muted">After</p>{side("insert")}</div>
    </div>
  );
}
