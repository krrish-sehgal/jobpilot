import type { ChatMessage, ConversationSummary, JobCard, JobDetail, ResumeSections, ResumeSummary, SentMessage, User } from "../types";
import { JOBS } from "./jobs";
import { SAMPLE_SECTIONS } from "./resumeSample";
import type { TailoringRecord } from "./tailoring";
import { nowIso } from "./util";

/** A turn waiting to be streamed. Created by sendMessage, consumed by streamTurn. */
export interface MockTurn {
  id: string;
  conversationId: string;
  userBody: string;
}

export interface MockResume {
  summary: ResumeSummary;
  sections: ResumeSections;
  failureReason: string | null;
  /** Epoch ms when parsing "finishes"; getResume reports `parsing` until then. */
  readyAt: number;
}

/** Everything the mock backend "stores". A plain module singleton: it survives client-side navigation and resets on reload. */
export const db = {
  user: {
    id: "user-demo",
    email: "",
    full_name: "Riya Calloway",
    seniority_band: "mid",
    preferred_location_tiers: ["remote", "hybrid"],
    has_resume: true,
    created_at: "2026-09-01T09:00:00Z",
  } as User,
  conversations: new Map<string, { summary: ConversationSummary; messages: ChatMessage[] }>(),
  saved: new Set<string>(["job-driftwood-fullstack"]),
  resumes: new Map<string, MockResume>(),
  tailorings: new Map<string, TailoringRecord>(),
  turns: new Map<string, MockTurn>(),
  /** "/fail" demo: conversation+message pairs whose first attempt already errored, so the retry (a fresh client_message_id) succeeds. */
  failedDemo: new Set<string>(),
  /** client_message_id -> original ids, which is what makes sendMessage idempotent. */
  sent: new Map<string, SentMessage>(),
};

export const jobById = (id: string): JobDetail | undefined => JOBS.find((j) => j.job_id === id);

/** Stamps the current saved flag onto a card so every read agrees with save/unsave. */
export const withSaved = <T extends JobCard>(card: T): T => ({ ...card, is_saved: db.saved.has(card.job_id) });

export function primaryResume(): MockResume | undefined {
  return [...db.resumes.values()].find((r) => r.summary.is_primary && r.summary.status === "ready");
}

// ---------- seed ----------

function seed() {
  db.resumes.set("resume-seed", {
    summary: {
      id: "resume-seed",
      file_name: "Riya_Calloway_Resume.pdf",
      status: "ready",
      is_primary: true,
      uploaded_at: "2026-09-02T10:00:00Z",
    },
    sections: SAMPLE_SECTIONS,
    failureReason: null,
    readyAt: 0,
  });

  const first = JOBS[0]!;
  const card: JobCard = { ...first, match_score: 91, match_reasons: ["Python and PostgreSQL on your resume", "Remote, matching your preference"] };
  db.conversations.set("conv-seed", {
    summary: {
      id: "conv-seed",
      title: "Remote backend roles",
      last_message_preview: "I found a strong remote backend match.",
      updated_at: "2026-11-10T08:30:00Z",
    },
    messages: [
      { id: "m-seed-1", role: "user", body: "Show me remote backend roles", job_cards: [], tailoring_id: null, created_at: "2026-11-10T08:29:00Z" },
      {
        id: "m-seed-2",
        role: "assistant",
        body: "I found a strong remote backend match. **Lumenfold** is hiring a senior engineer to own their ledger pipeline, which lines up with your Python and PostgreSQL work.",
        job_cards: [card],
        tailoring_id: null,
        created_at: nowIso(),
      },
    ],
  });
}
seed();
