import { FileText, MessageSquareText, Search, Sparkles, type LucideIcon } from "lucide-react";
import { LinkButton } from "@/components/ui/Button";

const steps: { icon: LucideIcon; title: string; body: string }[] = [
  { icon: MessageSquareText, title: "1. Chat", body: "Describe the role, seniority and where you want to work. Follow up the way you would with a recruiter friend." },
  { icon: Search, title: "2. Matches", body: "The agent calls a search tool, ranks live postings against your resume and shows each score with the reasons behind it." },
  { icon: FileText, title: "3. Tailored resume", body: "Pick a role and get suggested edits for your summary, bullets and skills. Accept or reject each one and export." },
];

export function HowItWorks() {
  return (
    <section id="how" className="border-y border-line bg-surface">
      <div className="mx-auto max-w-6xl px-6 py-20">
        <h2 className="font-display text-4xl">From a sentence to an application</h2>
        <ol className="mt-10 grid gap-6 md:grid-cols-3">
          {steps.map((s) => (
            <li key={s.title} className="rounded-xl border border-line bg-paper p-6">
              <s.icon className="h-6 w-6 text-brand" aria-hidden />
              <h3 className="mt-4 font-display text-xl">{s.title}</h3>
              <p className="mt-2 text-sm text-muted">{s.body}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

export function Features() {
  return (
    <section className="mx-auto max-w-6xl space-y-20 px-6 py-20">
      <div className="grid items-center gap-10 md:grid-cols-2">
        <div>
          <p className="font-mono text-xs uppercase tracking-widest text-signal">Show your work</p>
          <h2 className="mt-3 font-display text-4xl">An agent you can watch think</h2>
          <p className="mt-4 text-muted">Every reply streams live. You see which tools the agent is calling (&ldquo;Searching remote backend roles&rdquo;, &ldquo;Found 6 matching roles&rdquo;) before the answer arrives, so nothing is a black box.</p>
        </div>
        <ul className="space-y-3 rounded-2xl border border-line bg-surface p-6 font-mono text-sm">
          <li className="text-good">&#10003; Recalled 2 preferences</li>
          <li className="text-good">&#10003; Read Riya_Calloway_Resume.pdf</li>
          <li className="text-good">&#10003; Found 6 matching roles</li>
          <li className="text-muted">&#8230; writing reply<span className="animate-blink">_</span></li>
        </ul>
      </div>
      <div className="grid items-center gap-10 md:grid-cols-2">
        <div className="space-y-2 rounded-2xl border border-line bg-surface p-6 text-sm md:order-first">
          <p className="text-muted line-through decoration-bad/60">Wrote database queries and improved slow endpoints.</p>
          <p><mark className="rounded bg-good/15 px-1 text-ink">Profiled and optimized</mark> slow database queries, cutting p95 latency by <mark className="rounded bg-good/15 px-1 text-ink">38%</mark>.</p>
        </div>
        <div>
          <p className="font-mono text-xs uppercase tracking-widest text-signal">You decide</p>
          <h2 className="mt-3 font-display text-4xl">Edits you can accept one by one</h2>
          <p className="mt-4 text-muted">Tailoring never silently rewrites your resume. Each suggestion shows a word-level diff and the reason for it. Accept, reject, preview the result, then export.</p>
        </div>
      </div>
    </section>
  );
}

export function Cta() {
  return (
    <section className="px-6 pb-24">
      <div className="mx-auto max-w-4xl rounded-3xl bg-brand px-8 py-14 text-center text-brand-ink">
        <Sparkles className="mx-auto h-6 w-6 text-signal" aria-hidden />
        <h2 className="mt-4 font-display text-4xl">Ready when you are</h2>
        <p className="mx-auto mt-3 max-w-lg opacity-80">Upload your resume, say what you are looking for, and let JobPilot do the legwork.</p>
        <LinkButton href="/login" size="lg" variant="secondary" className="mt-8 !border-transparent">Get started</LinkButton>
      </div>
    </section>
  );
}
