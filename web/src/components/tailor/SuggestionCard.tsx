import { Check, X } from "lucide-react";
import type { Suggestion } from "@/lib/api/types";
import { cn } from "@/lib/cn";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { DiffText } from "./DiffText";

const kindLabel: Record<Suggestion["kind"], string> = {
  rewrite_bullet: "Rewrite bullet",
  rewrite_summary: "Rewrite summary",
  add_skill: "Add skill",
  reorder_section: "Reorder items",
};

/** One proposed edit with its reason, a diff, and Accept / Reject. */
export function SuggestionCard({
  suggestion: s, mode, onAccept, onReject,
}: {
  suggestion: Suggestion;
  mode: "inline" | "split";
  onAccept: () => void;
  onReject: () => void;
}) {
  return (
    <li
      className={cn(
        "rounded-xl border bg-surface p-4",
        s.decision === "accepted" && "border-good/50",
        s.decision === "rejected" && "border-line opacity-60",
        s.decision === "pending" && "border-line",
      )}
    >
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="brand">{kindLabel[s.kind]}</Badge>
        <span className="text-xs capitalize text-muted">{s.section}</span>
        {s.decision !== "pending" ? <Badge tone={s.decision === "accepted" ? "good" : "neutral"}>{s.decision}</Badge> : null}
      </div>

      <div className="mt-3">
        {s.kind === "add_skill" ? (
          <p className="text-sm">Add <ins className="rounded bg-good/15 px-1 font-medium no-underline">{s.proposed}</ins> to your skills.</p>
        ) : s.kind === "reorder_section" ? (
          <p className="text-sm"><span className="text-muted line-through">{s.original}</span><br />{s.proposed}</p>
        ) : (
          <DiffText before={s.original ?? ""} after={s.proposed} mode={mode} />
        )}
      </div>

      <p className="mt-3 text-sm text-muted">{s.reason}</p>
      {s.keywords_added.length > 0 ? (
        <ul className="mt-2 flex flex-wrap gap-1.5" aria-label="Keywords added">
          {s.keywords_added.map((k) => <li key={k}><Badge tone="good">+ {k}</Badge></li>)}
        </ul>
      ) : null}

      <div className="mt-4 flex gap-2">
        <Button size="sm" variant={s.decision === "accepted" ? "primary" : "secondary"} aria-pressed={s.decision === "accepted"} onClick={onAccept} icon={<Check className="h-4 w-4" aria-hidden />}>Accept</Button>
        <Button size="sm" variant={s.decision === "rejected" ? "danger" : "secondary"} aria-pressed={s.decision === "rejected"} onClick={onReject} icon={<X className="h-4 w-4" aria-hidden />}>Reject</Button>
      </div>
    </li>
  );
}
