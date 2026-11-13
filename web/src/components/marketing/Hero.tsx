import { ArrowRight } from "lucide-react";
import { LinkButton } from "@/components/ui/Button";
import { ProductPreview } from "./ProductPreview";

export function Hero() {
  return (
    <section className="relative overflow-hidden">
      <div className="grid-paper absolute inset-0 -z-10" aria-hidden />
      <div className="mx-auto grid max-w-6xl gap-12 px-6 pb-20 pt-16 lg:grid-cols-[1.05fr_0.95fr] lg:items-center lg:pt-24">
        <div>
          <p className="mb-5 inline-flex items-center gap-2 rounded-full border border-line bg-surface px-3 py-1 font-mono text-xs uppercase tracking-widest text-muted">
            <span className="h-1.5 w-1.5 rounded-full bg-signal" aria-hidden /> Cleared for takeoff
          </p>
          <h1 className="font-display text-5xl leading-[1.05] tracking-tight sm:text-6xl">
            Your job search, <em className="text-brand">on autopilot</em>. You stay in command.
          </h1>
          <p className="mt-6 max-w-xl text-lg text-muted">
            Tell JobPilot what you want in plain English. An agent searches live postings, explains why each one fits you, and rewrites your resume for the roles you pick.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <LinkButton href="/login" size="lg">Start a conversation <ArrowRight className="h-4 w-4" aria-hidden /></LinkButton>
            <LinkButton href="#how" variant="secondary" size="lg">See how it works</LinkButton>
          </div>
          <p className="mt-4 text-sm text-muted">Free to try. Sign in with a one-time code, no password.</p>
        </div>
        <ProductPreview />
      </div>
    </section>
  );
}
