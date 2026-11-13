import type { StreamState } from "@/hooks/useChatStream";
import { Markdown } from "@/lib/markdown";
import { JobCardCarousel } from "@/components/jobs/JobCardList";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { ToolActivityList } from "./ToolActivity";
import { TailoringCard } from "./TailoringCard";

const phaseText = { thinking: "Thinking", calling_tool: "Working", writing: "Writing" } as const;

/**
 * The reply while it is still arriving. The text region is `aria-live="polite"`
 * so screen readers announce new sentences without interrupting; `aria-busy`
 * tells them the content is incomplete.
 */
export function StreamingBubble({ state, onRetry }: { state: StreamState; onRetry: () => void }) {
  if (state.status === "idle") return null;
  const streaming = state.status === "active";

  return (
    <div className="space-y-3 animate-rise" data-testid="streaming-bubble">
      <ToolActivityList tools={state.tools} />

      <div aria-live="polite" aria-busy={streaming} className="max-w-[48rem]">
        {state.text ? (
          <>
            <Markdown source={state.text} />
            {streaming ? <span className="ml-0.5 inline-block h-4 w-1.5 translate-y-0.5 animate-blink bg-brand" aria-hidden /> : null}
          </>
        ) : streaming && state.tools.length === 0 ? (
          <p className="text-sm text-muted">{state.agentPhase ? phaseText[state.agentPhase] : "Thinking"}&hellip;</p>
        ) : null}
      </div>

      {state.cards.length > 0 ? <JobCardCarousel jobs={state.cards} /> : null}
      {state.tailoring ? <TailoringCard tailoringId={state.tailoring.tailoringId} /> : null}

      {state.status === "error" && state.error ? (
        <ErrorNotice message={state.error.message} onRetry={state.error.retryable ? onRetry : undefined} retryLabel="Retry" />
      ) : null}
    </div>
  );
}
