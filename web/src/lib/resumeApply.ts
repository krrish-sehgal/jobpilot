import type { ResumeSections, Suggestion } from "@/lib/api/types";

export type SectionKey = "summary" | "experience" | "projects" | "skills" | "education";
export const DEFAULT_ORDER: SectionKey[] = ["summary", "experience", "projects", "skills", "education"];

export interface AppliedResume {
  sections: ResumeSections;
  order: SectionKey[];
  /** Ids of bullets / "summary" / "skills:<term>" that changed, so the preview can highlight them. */
  changed: Set<string>;
}

/**
 * Produces the resume as it would look with the *accepted* suggestions applied.
 * Pure, so the live preview, the mock exporter and tests share one definition.
 *
 * Contract note: for `reorder_section`, `proposed` is the new section order as a
 * comma-separated list ("skills, experience, projects, education").
 */
export function applySuggestions(base: ResumeSections, suggestions: Suggestion[]): AppliedResume {
  const sections: ResumeSections = structuredClone(base);
  let order = [...DEFAULT_ORDER];
  const changed = new Set<string>();

  for (const s of suggestions) {
    if (s.decision !== "accepted") continue;
    switch (s.kind) {
      case "rewrite_summary":
        sections.summary = s.proposed;
        changed.add("summary");
        break;
      case "rewrite_bullet":
        for (const bullet of [...sections.experience, ...sections.projects].flatMap((x) => x.bullets)) {
          if (bullet.id === s.target_id) {
            bullet.text = s.proposed;
            changed.add(bullet.id);
          }
        }
        break;
      case "add_skill":
        if (!sections.skills.some((k) => k.toLowerCase() === s.proposed.toLowerCase())) {
          sections.skills.push(s.proposed);
          changed.add(`skills:${s.proposed}`);
        }
        break;
      case "reorder_section": {
        const wanted = s.proposed.split(",").map((p) => p.trim()).filter((p): p is SectionKey => DEFAULT_ORDER.includes(p as SectionKey));
        order = [...wanted, ...order.filter((o) => !wanted.includes(o))];
        break;
      }
    }
  }
  return { sections, order, changed };
}

/** Plain-text rendering, used by the mock exporter. */
export function resumeToPlainText({ sections, order }: AppliedResume): string[] {
  const lines: string[] = [sections.contact.name];
  const contact = [sections.contact.email, sections.contact.phone, sections.contact.location].filter(Boolean);
  lines.push(contact.join("  |  "), "");
  for (const key of order) {
    if (key === "summary" && sections.summary) lines.push("SUMMARY", sections.summary, "");
    if (key === "experience") {
      lines.push("EXPERIENCE");
      for (const e of sections.experience) {
        lines.push(`${e.title}, ${e.company} (${e.start} - ${e.end ?? "present"})`);
        e.bullets.forEach((b) => lines.push(`  - ${b.text}`));
      }
      lines.push("");
    }
    if (key === "projects") {
      lines.push("PROJECTS");
      for (const p of sections.projects) {
        lines.push(`${p.name} (${p.tech.join(", ")})`);
        p.bullets.forEach((b) => lines.push(`  - ${b.text}`));
      }
      lines.push("");
    }
    if (key === "skills") lines.push("SKILLS", sections.skills.join(", "), "");
    if (key === "education") {
      lines.push("EDUCATION");
      sections.education.forEach((e) => lines.push(`${e.degree}, ${e.institution} ${e.end ?? ""}`.trim()));
      lines.push("");
    }
  }
  return lines;
}
