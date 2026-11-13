import type { KeywordCoverage, ResumeSections, Suggestion, Tailoring } from "../types";
import { db, jobById, type MockResume } from "./db";
import { newId, nowIso } from "./util";

/** How long the mock keeps a tailoring in `running` so the polling UI is visible. */
const RUN_MS = 2800;

/** Terms we recognise in a pasted job description. Real scoring lives in the backend. */
const KNOWN_TERMS = [
  "Python", "TypeScript", "React", "Go", "Kubernetes", "PostgreSQL", "AWS", "Terraform", "Kafka", "SQL",
  "Docker", "GraphQL", "Airflow", "Spark", "Node.js", "CI/CD", "Observability", "gRPC",
];

export interface TailoringRecord {
  id: string;
  resumeId: string;
  jobId: string | null;
  jobTitle: string;
  company: string | null;
  createdAt: string;
  readyAt: number;
  keywordSeeds: KeywordCoverage[];
  scoreBefore: number;
  suggestions: Suggestion[];
}

const lower = (s: string) => s.toLowerCase();

function resumeText(r: ResumeSections): string {
  const parts = [r.summary ?? "", ...r.skills, ...r.experience.flatMap((e) => e.bullets.map((b) => b.text)), ...r.projects.flatMap((p) => [...p.tech, ...p.bullets.map((b) => b.text)])];
  return lower(parts.join(" "));
}

function extractTerms(jd: string): string[] {
  const text = lower(jd);
  const hits = KNOWN_TERMS.filter((t) => text.includes(lower(t)));
  return hits.length >= 3 ? hits : [...hits, ...["Python", "PostgreSQL", "AWS", "Kafka"].filter((t) => !hits.includes(t))].slice(0, 6);
}

function buildSuggestions(sections: ResumeSections, missing: string[], jobTitle: string): Suggestion[] {
  const kw = (i: number) => missing[i] ?? missing[0] ?? "automated testing";
  const mk = (s: Omit<Suggestion, "id" | "decision">): Suggestion => ({ ...s, id: newId(), decision: "pending" });
  const bullet = (id: string) => sections.experience.flatMap((e) => e.bullets).find((b) => b.id === id)?.text ?? null;

  const out: Suggestion[] = [
    mk({
      kind: "rewrite_summary", target_id: "summary", section: "summary", original: sections.summary,
      proposed: `Backend engineer with three years of experience building and operating production services, now targeting a ${jobTitle} role. Strongest in ${sections.skills.slice(0, 2).join(" and ")}, with growing depth in ${missing.slice(0, 2).join(" and ") || "distributed systems"}.`,
      reason: "Names the target role and leads with the skills the posting asks for first.",
      keywords_added: missing.slice(0, 2),
    }),
    mk({
      kind: "rewrite_bullet", target_id: "b-1", section: "experience", original: bullet("b-1"),
      proposed: `Designed and shipped REST APIs for the billing module serving 40 enterprise customers, applying ${kw(0)} to keep payment handling reliable.`,
      reason: "Adds a concrete scope and the first missing required keyword.", keywords_added: [kw(0)],
    }),
    mk({
      kind: "rewrite_bullet", target_id: "b-2", section: "experience", original: bullet("b-2"),
      proposed: `Profiled and optimized slow database queries, cutting p95 endpoint latency by 38% and page load time by 1.2 s, backed by ${kw(1)}.`,
      reason: "Replaces a vague outcome with measurable ones.", keywords_added: [kw(1)],
    }),
    mk({
      kind: "rewrite_bullet", target_id: "b-3", section: "experience", original: bullet("b-3"),
      proposed: `Deployed services and led triage of production incidents, using ${kw(2)} to shorten time to recovery from hours to minutes.`,
      reason: "Shows ownership of on-call work, which this role emphasises.", keywords_added: [kw(2)],
    }),
  ];
  missing.slice(3, 4).forEach((term) =>
    out.push(mk({ kind: "add_skill", target_id: null, section: "skills", original: null, proposed: term, reason: `"${term}" appears in the posting but nowhere on your resume.`, keywords_added: [term] })),
  );
  out.push(
    mk({
      kind: "reorder_section", target_id: "skills", section: "skills",
      original: "summary, experience, projects, skills, education",
      proposed: "summary, skills, experience, projects, education",
      reason: "Your skills line up well with this posting, so recruiters should see it earlier.", keywords_added: [],
    }),
  );
  return out;
}

export function startTailoring(resume: MockResume, input: { jobId?: string; jobDescriptionText?: string }): string {
  const job = input.jobId ? jobById(input.jobId) : undefined;
  const terms = job ? job.skills : extractTerms(input.jobDescriptionText ?? "");
  const text = resumeText(resume.sections);
  const keywordSeeds: KeywordCoverage[] = terms.map((term, i) => ({
    term, importance: i < 3 ? "required" : "preferred", found_in_resume: text.includes(lower(term)), covered_after: false,
  }));
  const missing = keywordSeeds.filter((k) => !k.found_in_resume).map((k) => k.term);
  const firstLine = (input.jobDescriptionText ?? "").split("\n")[0]?.trim().slice(0, 60);
  const jobTitle = job?.title ?? (firstLine || "Custom role");

  const weight = (k: KeywordCoverage) => (k.importance === "required" ? 2 : 1);
  const total = keywordSeeds.reduce((n, k) => n + weight(k), 0) || 1;
  const found = keywordSeeds.filter((k) => k.found_in_resume).reduce((n, k) => n + weight(k), 0);

  const id = newId();
  db.tailorings.set(id, {
    id, resumeId: resume.summary.id, jobId: job?.job_id ?? null, jobTitle, company: job?.company ?? null,
    createdAt: nowIso(), readyAt: Date.now() + RUN_MS, keywordSeeds,
    scoreBefore: Math.round(35 + (found / total) * 40),
    suggestions: buildSuggestions(resume.sections, missing, jobTitle),
  });
  return id;
}

/**
 * Derives the contract-shaped Tailoring from a stored record.
 * `score_after` is the *projected* score if every non-rejected suggestion is
 * applied; rejecting one visibly lowers it (see web/README.md, "Ambiguities").
 */
export function viewTailoring(rec: TailoringRecord): Tailoring {
  const running = Date.now() < rec.readyAt;
  const live = rec.suggestions.filter((s) => s.decision !== "rejected");
  const added = new Set(live.flatMap((s) => s.keywords_added.map(lower)));
  const gain = live.reduce((n, s) => n + 3 + s.keywords_added.length * 3, 0);
  return {
    id: rec.id, resume_id: rec.resumeId, job_id: rec.jobId, job_title: rec.jobTitle, company: rec.company,
    status: running ? "running" : "ready",
    score_before: rec.scoreBefore,
    score_after: running ? rec.scoreBefore : Math.min(96, rec.scoreBefore + gain),
    keywords: rec.keywordSeeds.map((k) => ({ ...k, covered_after: !running && (k.found_in_resume || added.has(lower(k.term))) })),
    suggestions: running ? [] : rec.suggestions,
    created_at: rec.createdAt,
  };
}
