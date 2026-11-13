import type {
  AuthSession,
  ChatMessage,
  ConversationSummary,
  CreateTailoringInput,
  ExportFormat,
  ExportedFile,
  JobCard,
  JobDetail,
  Resume,
  ResumeSummary,
  SentMessage,
  StreamEvent,
  Tailoring,
  User,
} from "./types";

/**
 * The one interface the UI programs against. There are two implementations:
 *  - HttpApiClient (./http.ts)  talks to the real backend (docs/web-api.md)
 *  - MockApiClient (./mock/)    seeded in-memory data, no network at all
 * Components import `api` from "@/lib/api" and never learn which one they got.
 */
export interface ApiClient {
  // --- auth ---
  requestCode(email: string): Promise<void>;
  verifyCode(email: string, code: string): Promise<AuthSession>;
  me(): Promise<User>;

  // --- chat ---
  listConversations(): Promise<ConversationSummary[]>;
  createConversation(): Promise<ConversationSummary>;
  listMessages(conversationId: string): Promise<ChatMessage[]>;
  /** Idempotent on `clientMessageId`: resending returns the original ids. */
  sendMessage(conversationId: string, body: string, clientMessageId: string): Promise<SentMessage>;
  /** Yields validated stream events until `done`/`error` or until `signal` aborts. */
  streamTurn(conversationId: string, turnId: string, signal: AbortSignal): AsyncGenerator<StreamEvent>;

  // --- jobs ---
  getJob(jobId: string): Promise<JobDetail>;
  saveJob(jobId: string): Promise<void>;
  unsaveJob(jobId: string): Promise<void>;
  listSavedJobs(): Promise<JobCard[]>;

  // --- resumes ---
  /** `onProgress` receives 0..1 while the file bytes are uploading. */
  uploadResume(file: File, onProgress: (fraction: number) => void, signal?: AbortSignal): Promise<{ resumeId: string }>;
  listResumes(): Promise<ResumeSummary[]>;
  getResume(resumeId: string): Promise<Resume>;
  makePrimary(resumeId: string): Promise<void>;

  // --- tailoring ---
  createTailoring(input: CreateTailoringInput): Promise<{ tailoringId: string }>;
  getTailoring(tailoringId: string): Promise<Tailoring>;
  submitDecisions(tailoringId: string, accepted: string[], rejected: string[]): Promise<Tailoring>;
  exportTailoring(tailoringId: string, format: ExportFormat): Promise<ExportedFile>;
}
