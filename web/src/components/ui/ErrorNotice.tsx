import { AlertTriangle } from "lucide-react";
import { Button } from "./Button";

/** Inline error with an optional retry. `role="alert"` announces it immediately. */
export function ErrorNotice({
  message,
  onRetry,
  retryLabel = "Try again",
}: {
  message: string;
  onRetry?: () => void;
  retryLabel?: string;
}) {
  return (
    <div role="alert" className="flex items-start gap-3 rounded-lg border border-bad/30 bg-bad/5 p-3 text-sm">
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-bad" aria-hidden />
      <p className="flex-1">{message}</p>
      {onRetry ? (
        <Button size="sm" variant="secondary" onClick={onRetry}>
          {retryLabel}
        </Button>
      ) : null}
    </div>
  );
}
