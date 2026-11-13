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
 * Stable reorder: items named in `wanted` (lower-case) come first in that order; items the list
 * doesn't mention keep their relative order at the end.
 */
export function sortByWanted<T>(items: T[], wanted: string[], nameOf: (item: T) => string): T[] {
  const rank = (item: T) => {
    const i = wanted.indexOf(nameOf(item).toLowerCase());
    return i === -1 ? wanted.length : i;
  };
  return items
    .map((item, index) => ({ item, index }))
    .sort((a, b) => rank(a.item) - rank(b.item) || a.index - b.index)
    .map((x) => x.item);
}

/**
 * Produces the resume as it would look with the *accepted* suggestions applied.
 * Pure, so the live preview, the mock exporter and tests share one definition.
 *
 * Contract (docs/web-api.md, "Suggestion semantics"): for `reorder_section`, `section` is
 * "skills" or "projects" and `proposed` lists that section's items (skill names or project
 * names), comma-separated, most relevant first. Section order itself never changes.
 */
export function applySuggestions(base: ResumeSections, suggestions: Suggestion[]): AppliedResume {
  const sections: ResumeSections = structuredClone(base);
  const order = [...DEFAULT_ORDER];
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
        const wanted = s.proposed.split(",").map((item) => item.trim().toLowerCase()).filter(Boolean);
        if (s.section === "skills") sections.skills = sortByWanted(sections.skills, wanted, (skill) => skill);
        else if (s.section === "projects") sections.projects = sortByWanted(sections.projects, wanted, (project) => project.name);
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
