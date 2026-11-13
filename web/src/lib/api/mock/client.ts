import type { ApiClient } from "../client";
import { ApiError } from "../errors";
import type { AuthSession, ChatMessage, ConversationSummary, CreateTailoringInput, ExportFormat, ExportedFile, JobCard, JobDetail, Resume, ResumeSummary, SentMessage, StreamEvent, Tailoring, User } from "../types";
import { applySuggestions, resumeToPlainText } from "@/lib/resumeApply";
import { runTurn } from "./agent";
import { db, jobById, withSaved } from "./db";
import { JOBS } from "./jobs";
import { SAMPLE_SECTIONS } from "./resumeSample";
import { startTailoring, viewTailoring } from "./tailoring";
import { buildPdf, buildRtf } from "./exportFiles";
import { newId, nowIso, sleep } from "./util";

/** Simulated latency so loading states are visible. */
const LATENCY = 220;
const PARSE_MS = 2600;

const notFound = (what: string) => new ApiError("not_found", `${what} not found`, 404);

/** Implements the same ApiClient as the HTTP client, entirely in memory. See web/README.md. */
export class MockApiClient implements ApiClient {
  // ---------- auth ----------
  async requestCode(email: string) {
    await sleep(LATENCY);
    if (!/^\S+@\S+\.\S+$/.test(email)) throw new ApiError("validation_failed", "Enter a valid email address.", 422);
  }
  async verifyCode(email: string, code: string): Promise<AuthSession> {
    await sleep(LATENCY);
    // Any 6-digit code works except 000000, so the error state can be demoed.
    if (!/^\d{6}$/.test(code) || code === "000000") throw new ApiError("validation_failed", "That code is incorrect or expired.", 422);
    db.user.email = email;
    return { access_token: `mock-${newId("tok")}`, expires_at: new Date(Date.now() + 8 * 3600_000).toISOString(), user: { ...db.user } };
  }
  async me(): Promise<User> {
    await sleep(80);
    return { ...db.user, email: db.user.email || "demo@example.com" };
  }

  // ---------- chat ----------
  async listConversations(): Promise<ConversationSummary[]> {
    await sleep(LATENCY);
    return [...db.conversations.values()].map((c) => c.summary).sort((a, b) => b.updated_at.localeCompare(a.updated_at));
  }
  async createConversation(): Promise<ConversationSummary> {
    await sleep(80);
    const summary: ConversationSummary = { id: newId("conv"), title: "New conversation", last_message_preview: null, updated_at: nowIso() };
    db.conversations.set(summary.id, { summary, messages: [] });
    return summary;
  }
  async listMessages(id: string): Promise<ChatMessage[]> {
    await sleep(LATENCY);
    const conv = db.conversations.get(id);
    if (!conv) throw notFound("Conversation");
    return conv.messages.map((m) => ({ ...m, job_cards: m.job_cards.map(withSaved) }));
  }
  async sendMessage(id: string, body: string, clientMessageId: string): Promise<SentMessage> {
    await sleep(120);
    const existing = db.sent.get(clientMessageId);
    if (existing) return existing; // idempotent retry: same turn, no duplicate message
    const conv = db.conversations.get(id);
    if (!conv) throw notFound("Conversation");
    const message: ChatMessage = { id: newId("msg"), role: "user", body, job_cards: [], tailoring_id: null, created_at: nowIso() };
    conv.messages.push(message);
    if (conv.summary.title === "New conversation") conv.summary.title = body.slice(0, 40);
    conv.summary.updated_at = message.created_at;
    const turnId = newId("turn");
    db.turns.set(turnId, { id: turnId, conversationId: id, userBody: body, failedOnce: false });
    const ack = { message_id: message.id, turn_id: turnId };
    db.sent.set(clientMessageId, ack);
    return ack;
  }
  async *streamTurn(_conversationId: string, turnId: string, signal: AbortSignal): AsyncGenerator<StreamEvent> {
    const turn = db.turns.get(turnId);
    if (!turn) throw notFound("Turn");
    yield* runTurn(turn, signal);
  }

  // ---------- jobs ----------
  async getJob(id: string): Promise<JobDetail> {
    await sleep(LATENCY);
    const job = jobById(id);
    if (!job) throw notFound("Job");
    return { ...withSaved(job), match_score: 84, match_reasons: ["Your skills overlap with this posting", "Matches your location preferences"] };
  }
  async saveJob(id: string) { await sleep(120); db.saved.add(id); }
  async unsaveJob(id: string) { await sleep(120); db.saved.delete(id); }
  async listSavedJobs(): Promise<JobCard[]> {
    await sleep(LATENCY);
    return JOBS.filter((j) => db.saved.has(j.job_id)).map((j) => withSaved({ ...j, match_score: 80, match_reasons: ["Saved by you"] }));
  }

  // ---------- resumes ----------
  async uploadResume(file: File, onProgress: (f: number) => void, signal?: AbortSignal) {
    for (let i = 1; i <= 5; i++) {
      await sleep(110, signal);
      onProgress(i / 5);
    }
    const id = newId("resume");
    const failing = /fail/i.test(file.name); // demo hook: name a file "fail.pdf" to see the failed state
    const hadPrimary = [...db.resumes.values()].some((r) => r.summary.is_primary);
    db.resumes.set(id, {
      summary: { id, file_name: file.name, status: "parsing", is_primary: !hadPrimary, uploaded_at: nowIso() },
      sections: SAMPLE_SECTIONS,
      failureReason: failing ? "We couldn't find any readable text. Is this a scanned image?" : null,
      readyAt: Date.now() + PARSE_MS,
    });
    return { resumeId: id };
  }
  private resolve(id: string): Resume {
    const r = db.resumes.get(id);
    if (!r) throw notFound("Resume");
    const done = Date.now() >= r.readyAt;
    const status = !done ? "parsing" : r.failureReason ? "failed" : "ready";
    r.summary.status = status;
    return { ...r.summary, failure_reason: status === "failed" ? r.failureReason : null, sections: status === "ready" ? r.sections : null };
  }
  async listResumes(): Promise<ResumeSummary[]> {
    await sleep(LATENCY);
    return [...db.resumes.keys()].map((id) => this.resolve(id)).map(({ failure_reason: _f, sections: _s, ...s }) => (void _f, void _s, s)).sort((a, b) => b.uploaded_at.localeCompare(a.uploaded_at));
  }
  async getResume(id: string): Promise<Resume> {
    await sleep(150);
    return this.resolve(id);
  }
  async makePrimary(id: string) {
    await sleep(120);
    if (!db.resumes.has(id)) throw notFound("Resume");
    db.resumes.forEach((r, key) => (r.summary.is_primary = key === id));
  }

  // ---------- tailoring ----------
  async createTailoring(input: CreateTailoringInput) {
    await sleep(LATENCY);
    const resume = db.resumes.get(input.resume_id);
    if (!resume) throw notFound("Resume");
    if (this.resolve(input.resume_id).status !== "ready") throw new ApiError("resume_not_ready", "Resume is still parsing.", 409);
    const tailoringId = "job_id" in input ? startTailoring(resume, { jobId: input.job_id }) : startTailoring(resume, { jobDescriptionText: input.job_description_text });
    return { tailoringId };
  }
  async getTailoring(id: string): Promise<Tailoring> {
    await sleep(150);
    const rec = db.tailorings.get(id);
    if (!rec) throw notFound("Tailoring");
    return viewTailoring(rec);
  }
  async submitDecisions(id: string, accepted: string[], rejected: string[]): Promise<Tailoring> {
    await sleep(120);
    const rec = db.tailorings.get(id);
    if (!rec) throw notFound("Tailoring");
    for (const s of rec.suggestions) {
      if (accepted.includes(s.id)) s.decision = "accepted";
      else if (rejected.includes(s.id)) s.decision = "rejected";
    }
    return viewTailoring(rec);
  }
  async exportTailoring(id: string, format: ExportFormat): Promise<ExportedFile> {
    await sleep(400);
    const rec = db.tailorings.get(id);
    const resume = rec && db.resumes.get(rec.resumeId);
    if (!rec || !resume) throw notFound("Tailoring");
    const lines = resumeToPlainText(applySuggestions(resume.sections, rec.suggestions));
    // The mock can't build a real .docx (that needs zipping), so it serves RTF, which Word opens.
    return format === "pdf"
      ? { blob: buildPdf(lines), fileName: "tailored-resume.pdf" }
      : { blob: buildRtf(lines), fileName: "tailored-resume.rtf" };
  }
}
