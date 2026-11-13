import { Check, Minus, Plus } from "lucide-react";
import type { KeywordCoverage as Keyword } from "@/lib/api/types";
import { cn } from "@/lib/cn";

function Chip({ k }: { k: Keyword }) {
  // Three states: already on the resume, will be covered by the edits, still missing.
  const state = k.found_in_resume ? "have" : k.covered_after ? "added" : "missing";
  const Icon = state === "have" ? Check : state === "added" ? Plus : Minus;
  const text = { have: "On your resume", added: "Covered by your edits", missing: "Missing" }[state];
  return (
    <li
      title={text}
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium",
        state === "have" && "border-good/30 bg-good/10 text-good",
        state === "added" && "border-brand/30 bg-brand/10 text-brand",
        state === "missing" && "border-bad/30 bg-bad/10 text-bad",
      )}
    >
      <Icon className="h-3 w-3" aria-hidden />
      {k.term}
      <span className="sr-only">: {text}</span>
    </li>
  );
}

/** Keywords from the posting, split into required vs preferred. */
export function KeywordCoverage({ keywords }: { keywords: Keyword[] }) {
  const groups: { title: string; items: Keyword[] }[] = [
    { title: "Required", items: keywords.filter((k) => k.importance === "required") },
    { title: "Preferred", items: keywords.filter((k) => k.importance === "preferred") },
  ];
  return (
    <section aria-label="Keyword coverage" className="rounded-xl border border-line bg-surface p-5">
      <h2 className="font-display text-xl">Keyword coverage</h2>
      <div className="mt-3 space-y-3">
        {groups.filter((g) => g.items.length).map((g) => (
          <div key={g.title}>
            <h3 className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-muted">{g.title}</h3>
            <ul className="flex flex-wrap gap-1.5">{g.items.map((k) => <Chip key={k.term} k={k} />)}</ul>
          </div>
        ))}
      </div>
    </section>
  );
}
