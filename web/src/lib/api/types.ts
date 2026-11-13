import type { z } from "zod";
import type * as s from "./schemas";

/*
  Domain types are *derived* from the zod schemas, so the runtime check and the
  compile-time type can never disagree. Request-only shapes (which we build
  ourselves and never parse) are declared by hand below.
*/

export type RoleCategory = z.infer<typeof s.roleCategory>;
export type SeniorityBand = z.infer<typeof s.seniorityBand>;
export type LocationTier = z.infer<typeof s.locationTier>;
export type EmploymentType = z.infer<typeof s.employmentType>;
export type ToolName = z.infer<typeof s.toolName>;

export type User = z.infer<typeof s.user>;
export type AuthSession = z.infer<typeof s.authSession>;
export type JobCard = z.infer<typeof s.jobCard>;
export type JobDetail = z.infer<typeof s.jobDetail>;
export type ConversationSummary = z.infer<typeof s.conversationSummary>;
export type ChatMessage = z.infer<typeof s.chatMessage>;
export type SentMessage = z.infer<typeof s.sentMessage>;
export type StreamEvent = z.infer<typeof s.streamEvent>;
export type ResumeStatus = z.infer<typeof s.resumeStatus>;
export type ResumeSummary = z.infer<typeof s.resumeSummary>;
export type Resume = z.infer<typeof s.resume>;
export type ResumeSections = z.infer<typeof s.resumeSections>;
export type Tailoring = z.infer<typeof s.tailoring>;
export type Suggestion = z.infer<typeof s.suggestion>;
export type KeywordCoverage = Tailoring["keywords"][number];

/** `POST /tailorings` takes either a stored job or pasted job-description text. */
export type CreateTailoringInput =
  | { resume_id: string; job_id: string }
  | { resume_id: string; job_description_text: string };

export type ExportFormat = "pdf" | "docx";

export interface ExportedFile {
  blob: Blob;
  fileName: string;
}
