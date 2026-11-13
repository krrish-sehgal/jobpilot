import type { JobCard, LocationTier, RoleCategory, SeniorityBand } from "../types";
import { withSaved, primaryResume } from "./db";
import { JOBS } from "./jobs";

/*
  A tiny stand-in for the real hybrid search + ranking engine: keyword hits
  against a few fields, plus overlap with the primary resume's skills. Good
  enough to make the demo respond to what you type.
*/

const TIER_WORDS: Record<string, LocationTier> = { remote: "remote", hybrid: "hybrid", onsite: "onsite", "on-site": "onsite" };
const LEVEL_WORDS: Record<string, SeniorityBand> = {
  intern: "intern", internship: "intern", junior: "entry", entry: "entry", fresher: "entry",
  mid: "mid", senior: "senior", staff: "senior", lead: "leadership",
};
const CATEGORY_WORDS: Record<string, RoleCategory> = {
  backend: "software_engineering", frontend: "software_engineering", engineer: "software_engineering", developer: "software_engineering",
  fullstack: "software_engineering", sre: "software_engineering", devops: "software_engineering",
  data: "data_and_analytics", analyst: "data_and_analytics", ml: "data_and_analytics",
  product: "product_and_design", design: "product_and_design", designer: "product_and_design", pm: "product_and_design",
  marketing: "marketing_and_growth", growth: "marketing_and_growth",
};

export interface ParsedQuery {
  tier?: LocationTier;
  level?: SeniorityBand;
  category?: RoleCategory;
  words: string[];
  /** Human text for tool labels: "remote senior software roles". */
  description: string;
}

export function parseQuery(text: string): ParsedQuery {
  const words = text.toLowerCase().replace(/[^a-z0-9+#.\s-]/g, " ").split(/\s+/).filter(Boolean);
  const find = <T,>(map: Record<string, T>) => words.map((w) => map[w]).find((v) => v !== undefined);
  const q: ParsedQuery = { tier: find(TIER_WORDS), level: find(LEVEL_WORDS), category: find(CATEGORY_WORDS), words, description: "" };
  const bits = [q.tier, q.level, words.find((w) => CATEGORY_WORDS[w]), "roles"].filter(Boolean);
  q.description = bits.join(" ");
  return q;
}

/** Whether the message looks like a search at all (vs. "hello"). */
export const isSearchIntent = (q: ParsedQuery) => Boolean(q.tier || q.level || q.category) || q.words.some((w) => ["job", "jobs", "role", "roles", "opening", "openings", "hiring", "find", "search", "show"].includes(w));

export function rankJobs(q: ParsedQuery, limit = 6): JobCard[] {
  const resumeSkills = new Set((primaryResume()?.sections.skills ?? []).map((s) => s.toLowerCase()));
  const scored = JOBS.map((job) => {
    let score = 52;
    const reasons: string[] = [];
    if (q.tier && job.location_tier === q.tier) { score += 14; reasons.push(q.tier === "remote" ? "Fully remote" : `Matches your ${q.tier} preference`); }
    if (q.level && job.seniority_band === q.level) { score += 12; reasons.push(`${q.level[0]!.toUpperCase()}${q.level.slice(1)}-level role`); }
    if (q.category && job.role_category === q.category) { score += 12; }
    const skillHits = job.skills.filter((s) => resumeSkills.has(s.toLowerCase()) || q.words.includes(s.toLowerCase()));
    if (skillHits.length) { score += Math.min(18, skillHits.length * 6); reasons.push(`Uses ${skillHits.slice(0, 3).join(", ")}`); }
    const textHit = q.words.some((w) => w.length > 3 && `${job.title} ${job.company}`.toLowerCase().includes(w));
    if (textHit) score += 6;
    if (!reasons.length) reasons.push("Close to your saved preferences");
    return withSaved({ ...job, match_score: Math.min(97, score), match_reasons: reasons.slice(0, 3) });
  });
  const filtered = scored.filter((j) => (!q.tier || j.location_tier === q.tier) && (!q.level || j.seniority_band === q.level) && (!q.category || j.role_category === q.category));
  const pool = filtered.length >= 2 ? filtered : scored;
  return pool.sort((a, b) => b.match_score - a.match_score).slice(0, limit).map(toCard);
}

/** Cards in chat omit the long description; strip the detail-only fields so payloads match the contract. */
function toCard(j: JobCard & { description?: string; employment_type?: string; min_years_experience?: number }): JobCard {
  const { description: _d, employment_type: _e, min_years_experience: _m, ...card } = j;
  void _d; void _e; void _m;
  return card;
}
