import { cn } from "@/lib/cn";

/**
 * Circular progress ring for match scores (0-100). Pure SVG so it needs no
 * chart library; the number is real text so screen readers get it too.
 */
export function ScoreRing({
  value,
  size = 52,
  label = "match",
  className,
}: {
  value: number;
  size?: number;
  label?: string;
  className?: string;
}) {
  const v = Math.max(0, Math.min(100, Math.round(value)));
  const stroke = 5;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const color = v >= 80 ? "text-good" : v >= 60 ? "text-brand" : "text-signal";

  return (
    <div
      className={cn("relative shrink-0", className)}
      style={{ width: size, height: size }}
      role="img"
      aria-label={`${v} percent ${label}`}
    >
      <svg width={size} height={size} className="-rotate-90" aria-hidden>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" strokeWidth={stroke} className="stroke-line" />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - v / 100)}
          className={cn("stroke-current transition-[stroke-dashoffset] duration-700", color)}
        />
      </svg>
      <span className="absolute inset-0 flex items-center justify-center text-sm font-semibold tabular-nums">{v}</span>
    </div>
  );
}
