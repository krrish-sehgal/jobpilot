import Link from "next/link";
import { cn } from "@/lib/cn";

/** Wordmark: a small paper-plane-on-a-flight-path glyph plus the name. */
export function Logo({ href = "/", className }: { href?: string; className?: string }) {
  return (
    <Link href={href} className={cn("inline-flex items-center gap-2 font-display text-xl", className)}>
      <svg width="26" height="26" viewBox="0 0 26 26" aria-hidden>
        <rect width="26" height="26" rx="7" className="fill-brand" />
        <path d="M5 18c4-1 7-4 9-9" className="stroke-brand-ink" strokeWidth="1.4" strokeDasharray="1.5 2.2" fill="none" />
        <path d="M14 7l6 2-5 4-1-6z" className="fill-signal" />
      </svg>
      <span>
        Job<span className="text-brand">Pilot</span>
      </span>
    </Link>
  );
}
