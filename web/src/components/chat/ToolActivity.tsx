import { AlertCircle, Check, Loader2 } from "lucide-react";
import type { ToolActivity as Tool } from "@/hooks/useChatStream";
import { cn } from "@/lib/cn";

/**
 * Live "what the agent is doing" list. A running tool shows its label
 * ("Searching remote backend roles..."); once finished it shows the summary
 * ("Found 6 matching roles") with a check.
 */
export function ToolActivityList({ tools }: { tools: Tool[] }) {
  if (tools.length === 0) return null;
  return (
    <ul className="space-y-1.5" aria-label="Agent activity">
      {tools.map((t) => (
        <li key={t.callId} className={cn("flex items-center gap-2 text-sm", t.status === "failed" ? "text-bad" : "text-muted")}>
          {t.status === "running" ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : t.status === "ok" ? <Check className="h-4 w-4 text-good" aria-hidden /> : <AlertCircle className="h-4 w-4" aria-hidden />}
          <span>{t.status === "running" ? `${t.label}…` : t.summary ?? t.label}</span>
        </li>
      ))}
    </ul>
  );
}
