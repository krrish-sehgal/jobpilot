import { z } from "zod";

/*
  Runtime schemas for every payload in docs/web-api.md. TypeScript types only
  exist at compile time, so a backend drift would otherwise surface as a
  confusing "undefined is not iterable" deep inside a component. Parsing at the
  boundary turns it into one clear `bad_response` error.
*/

export const roleCategory = z.enum([
  "software_engineering",
  "data_and_analytics",
  "product_and_design",
  "sales_and_business_dev",
  "marketing_and_growth",
  "operations_and_support",
  "finance_and_legal",
  "other",
]);
export const seniorityBand = z.enum(["intern", "entry", "mid", "senior", "leadership"]);
export const locationTier = z.enum(["remote", "hybrid", "onsite", "unknown"]);
export const employmentType = z.enum(["full_time", "part_time", "contract", "internship"]);

export const user = z.object({
  id: z.string(),
  email: z.string(),
  full_name: z.string().nullable(),
  seniority_band: seniorityBand.nullable(),
  preferred_location_tiers: z.array(locationTier),
  has_resume: z.boolean(),
  created_at: z.string(),
});

export const authSession = z.object({
  access_token: z.string(),
  expires_at: z.string(),
  user,
});

export const jobCard = z.object({
  job_id: z.string(),
  title: z.string(),
  company: z.string(),
  location_text: z.string().nullable(),
  location_tier: locationTier,
  seniority_band: seniorityBand,
  role_category: roleCategory,
  skills: z.array(z.string()),
  description_preview: z.string(),
  compensation_text: z.string().nullable(),
  apply_url: z.string(),
  match_score: z.number(),
  match_reasons: z.array(z.string()),
  posted_at: z.string().nullable(),
  is_saved: z.boolean(),
});

export const jobDetail = jobCard.extend({
  description: z.string(),
  employment_type: employmentType,
  min_years_experience: z.number(),
});

export const conversationSummary = z.object({
  id: z.string(),
  title: z.string(),
  last_message_preview: z.string().nullable(),
  updated_at: z.string(),
});

export const chatMessage = z.object({
  id: z.string(),
  role: z.enum(["user", "assistant"]),
  body: z.string(),
  job_cards: z.array(jobCard),
  tailoring_id: z.string().nullable(),
  created_at: z.string(),
});

export const sentMessage = z.object({ message_id: z.string(), turn_id: z.string() });

export const toolName = z.enum(["search_jobs", "recall_memory", "fetch_resume", "get_job_details", "tailor_resume"]);

/** The SSE events from the contract, as one discriminated union keyed by the `event:` name. */
export const streamEvent = z.discriminatedUnion("event", [
  z.object({ event: z.literal("status"), data: z.object({ phase: z.enum(["thinking", "calling_tool", "writing"]) }) }),
  z.object({
    event: z.literal("tool_call"),
    data: z.object({ call_id: z.string(), name: toolName, label: z.string() }),
  }),
  z.object({
    event: z.literal("tool_result"),
    data: z.object({ call_id: z.string(), name: toolName, ok: z.boolean(), summary: z.string() }),
  }),
  z.object({ event: z.literal("token"), data: z.object({ text: z.string() }) }),
  z.object({ event: z.literal("job_cards"), data: z.object({ cards: z.array(jobCard) }) }),
  z.object({
    event: z.literal("tailoring_started"),
    data: z.object({ tailoring_id: z.string(), job_id: z.string() }),
  }),
  z.object({ event: z.literal("done"), data: z.object({ message_id: z.string() }) }),
  z.object({
    event: z.literal("error"),
    data: z.object({ code: z.string(), message: z.string(), retryable: z.boolean() }),
  }),
]);

export const resumeStatus = z.enum(["parsing", "ready", "failed"]);

export const resumeSummary = z.object({
  id: z.string(),
  file_name: z.string(),
  status: resumeStatus,
  is_primary: z.boolean(),
  uploaded_at: z.string(),
});

const bullet = z.object({ id: z.string(), text: z.string() });

export const resumeSections = z.object({
  contact: z.object({
    name: z.string(),
    email: z.string().nullable(),
    phone: z.string().nullable(),
    location: z.string().nullable(),
    links: z.array(z.string()),
  }),
  summary: z.string().nullable(),
  experience: z.array(
    z.object({
      id: z.string(),
      company: z.string(),
      title: z.string(),
      start: z.string(),
      end: z.string().nullable(),
      bullets: z.array(bullet),
    }),
  ),
  education: z.array(
    z.object({
      id: z.string(),
      institution: z.string(),
      degree: z.string(),
      start: z.string().nullable(),
      end: z.string().nullable(),
      score: z.string().nullable(),
    }),
  ),
  projects: z.array(z.object({ id: z.string(), name: z.string(), bullets: z.array(bullet), tech: z.array(z.string()) })),
  skills: z.array(z.string()),
});

export const resume = resumeSummary.extend({
  failure_reason: z.string().nullable(),
  sections: resumeSections.nullable(),
});

export const resumeUploadAck = z.object({ resume_id: z.string(), status: z.literal("parsing") });

export const suggestion = z.object({
  id: z.string(),
  kind: z.enum(["rewrite_bullet", "rewrite_summary", "add_skill", "reorder_section"]),
  target_id: z.string().nullable(),
  section: z.enum(["summary", "experience", "projects", "skills"]),
  original: z.string().nullable(),
  proposed: z.string(),
  reason: z.string(),
  keywords_added: z.array(z.string()),
  decision: z.enum(["pending", "accepted", "rejected"]),
});

export const tailoring = z.object({
  id: z.string(),
  resume_id: z.string(),
  job_id: z.string().nullable(),
  job_title: z.string(),
  company: z.string().nullable(),
  status: z.enum(["running", "ready", "failed"]),
  score_before: z.number(),
  score_after: z.number(),
  keywords: z.array(
    z.object({
      term: z.string(),
      importance: z.enum(["required", "preferred"]),
      found_in_resume: z.boolean(),
      covered_after: z.boolean(),
    }),
  ),
  suggestions: z.array(suggestion),
  created_at: z.string(),
});

export const tailoringAck = z.object({ tailoring_id: z.string(), status: z.literal("running") });

export const apiErrorBody = z.object({ error: z.object({ code: z.string(), message: z.string() }) });

export const sentFlag = z.object({ sent: z.literal(true) });
