import { describe, expect, it } from "vitest";
import type { ResumeSections, Suggestion } from "@/lib/api/types";
import { applySuggestions, DEFAULT_ORDER, sortByWanted } from "./resumeApply";

const base: ResumeSections = {
  contact: { name: "A", email: null, phone: null, location: null },
  summary: "old",
  experience: [],
  projects: [
    { name: "Alpha", tech: [], bullets: [] },
    { name: "Beta", tech: [], bullets: [] },
    { name: "Gamma", tech: [], bullets: [] },
  ],
  skills: ["Python", "SQL", "Docker", "Git"],
  education: [],
} as unknown as ResumeSections;

const reorder = (section: "skills" | "projects", proposed: string, decision: Suggestion["decision"] = "accepted"): Suggestion => ({
  id: "s", kind: "reorder_section", target_id: section, section, original: null, proposed, reason: "", keywords_added: [], decision,
});

describe("sortByWanted", () => {
  it("puts wanted items first, case-insensitively, and keeps unknown items in order at the end", () => {
    expect(sortByWanted(["a", "B", "c", "d"], ["d", "b"], (x) => x)).toEqual(["d", "B", "a", "c"]);
  });
});

describe("applySuggestions reorder_section", () => {
  it("reorders skills", () => {
    const out = applySuggestions(base, [reorder("skills", "docker, PYTHON")]);
    expect(out.sections.skills).toEqual(["Docker", "Python", "SQL", "Git"]);
    expect(out.order).toEqual(DEFAULT_ORDER);
  });

  it("reorders projects and ignores unknown names", () => {
    const out = applySuggestions(base, [reorder("projects", "Gamma, Nope, Alpha")]);
    expect(out.sections.projects.map((p) => p.name)).toEqual(["Gamma", "Alpha", "Beta"]);
  });

  it("does nothing unless accepted", () => {
    expect(applySuggestions(base, [reorder("skills", "Git", "pending")]).sections.skills).toEqual(base.skills);
  });
});
