import { FileText, Star } from "lucide-react";
import type { ResumeSummary } from "@/lib/api/types";
import { timeAgo } from "@/lib/format";
import { cn } from "@/lib/cn";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";

const statusTone = { parsing: "signal", ready: "good", failed: "bad" } as const;

/** Uploaded resumes. Selecting one shows it on the right; "Make primary" tells the agent which one to use. */
export function ResumeList({
  resumes, selectedId, onSelect, onMakePrimary,
}: {
  resumes: ResumeSummary[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onMakePrimary: (id: string) => void;
}) {
  return (
    <ul className="space-y-2" aria-label="Your resumes">
      {resumes.map((r) => (
        <li key={r.id} className={cn("flex items-center gap-3 rounded-xl border bg-surface p-3", selectedId === r.id ? "border-brand" : "border-line")}>
          <button type="button" onClick={() => onSelect(r.id)} aria-pressed={selectedId === r.id} className="flex min-w-0 flex-1 items-center gap-3 rounded-lg text-left">
            <FileText className="h-5 w-5 shrink-0 text-muted" aria-hidden />
            <span className="min-w-0">
              <span className="block truncate text-sm font-medium">{r.file_name}</span>
              <span className="block text-xs text-muted">Uploaded {timeAgo(r.uploaded_at)}</span>
            </span>
          </button>
          <Badge tone={statusTone[r.status]}>{r.status}</Badge>
          {r.is_primary ? (
            <Badge tone="brand"><Star className="h-3 w-3" aria-hidden /> Primary</Badge>
          ) : r.status === "ready" ? (
            <Button size="sm" variant="secondary" onClick={() => onMakePrimary(r.id)}>Make primary</Button>
          ) : null}
        </li>
      ))}
    </ul>
  );
}
