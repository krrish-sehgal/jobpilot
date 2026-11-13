import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

type Tone = "neutral" | "brand" | "signal" | "good" | "bad";

const tones: Record<Tone, string> = {
  neutral: "bg-sunken text-muted border-line",
  brand: "bg-brand/10 text-brand border-brand/25",
  signal: "bg-signal/10 text-signal border-signal/30",
  good: "bg-good/10 text-good border-good/30",
  bad: "bg-bad/10 text-bad border-bad/30",
};

/** Small pill used for skills, match reasons, statuses and keywords. */
export function Badge({
  tone = "neutral",
  children,
  className,
  title,
}: {
  tone?: Tone;
  children: ReactNode;
  className?: string;
  title?: string;
}) {
  return (
    <span
      title={title}
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium",
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
