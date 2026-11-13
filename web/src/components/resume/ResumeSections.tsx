import type { ReactNode } from "react";
import type { ResumeSections } from "@/lib/api/types";
import { formatMonth } from "@/lib/format";
import { DEFAULT_ORDER, type SectionKey } from "@/lib/resumeApply";
import { Badge } from "@/components/ui/Badge";
import { cn } from "@/lib/cn";

/** A bullet or paragraph that gets a highlight when the tailoring changed it. */
function Changed({ on, children }: { on: boolean; children: ReactNode }) {
  return <span className={cn(on && "rounded bg-good/15 px-0.5")}>{children}</span>;
}

function Heading({ children }: { children: ReactNode }) {
  return <h3 className="mb-2 border-b border-line pb-1 font-mono text-xs font-semibold uppercase tracking-widest text-muted">{children}</h3>;
}

/**
 * Renders a parsed resume by section. Used both for the plain parsed view
 * (defaults) and for the tailoring live preview (custom `order` + `changed` highlights).
 */
export function ResumeSectionsView({
  sections,
  order = DEFAULT_ORDER,
  changed = new Set<string>(),
}: {
  sections: ResumeSections;
  order?: SectionKey[];
  changed?: Set<string>;
}) {
  const c = sections.contact;
  const blocks: Record<SectionKey, ReactNode> = {
    summary: sections.summary ? (
      <section key="summary"><Heading>Summary</Heading><p className="text-sm"><Changed on={changed.has("summary")}>{sections.summary}</Changed></p></section>
    ) : null,
    experience: (
      <section key="experience">
        <Heading>Experience</Heading>
        <div className="space-y-4">
          {sections.experience.map((e) => (
            <div key={e.id}>
              <p className="flex flex-wrap justify-between gap-x-3 text-sm font-medium"><span>{e.title}, {e.company}</span><span className="font-normal text-muted">{formatMonth(e.start)} - {formatMonth(e.end)}</span></p>
              <ul className="mt-1 list-disc space-y-1 pl-5 text-sm">{e.bullets.map((b) => <li key={b.id}><Changed on={changed.has(b.id)}>{b.text}</Changed></li>)}</ul>
            </div>
          ))}
        </div>
      </section>
    ),
    projects: sections.projects.length ? (
      <section key="projects">
        <Heading>Projects</Heading>
        <div className="space-y-3">
          {sections.projects.map((p) => (
            <div key={p.id}>
              <p className="text-sm font-medium">{p.name} <span className="font-normal text-muted">({p.tech.join(", ")})</span></p>
              <ul className="mt-1 list-disc space-y-1 pl-5 text-sm">{p.bullets.map((b) => <li key={b.id}><Changed on={changed.has(b.id)}>{b.text}</Changed></li>)}</ul>
            </div>
          ))}
        </div>
      </section>
    ) : null,
    skills: (
      <section key="skills">
        <Heading>Skills</Heading>
        <ul className="flex flex-wrap gap-1.5">{sections.skills.map((s) => <li key={s}><Badge tone={changed.has(`skills:${s}`) ? "good" : "neutral"}>{s}</Badge></li>)}</ul>
      </section>
    ),
    education: (
      <section key="education">
        <Heading>Education</Heading>
        <div className="space-y-2 text-sm">
          {sections.education.map((e) => (
            <p key={e.id} className="flex flex-wrap justify-between gap-x-3"><span><span className="font-medium">{e.degree}</span>, {e.institution}{e.score ? ` (${e.score})` : ""}</span><span className="text-muted">{e.start}{e.end ? ` - ${e.end}` : ""}</span></p>
          ))}
        </div>
      </section>
    ),
  };

  return (
    <div className="space-y-6">
      <header>
        <h2 className="font-display text-2xl">{c.name}</h2>
        <p className="mt-1 text-sm text-muted">{[c.email, c.phone, c.location, ...c.links].filter(Boolean).join("  ·  ")}</p>
      </header>
      {order.map((k) => blocks[k])}
    </div>
  );
}
