import { ApiError } from "@/lib/api/errors";

export const MAX_RESUME_BYTES = 5 * 1024 * 1024;
export const RESUME_ACCEPT =
  ".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document";

const ALLOWED_TYPES = new Set(["application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]);

/**
 * Client-side pre-check that mirrors the server's `file_too_large` and
 * `unsupported_file_type` errors, so the user gets instant feedback without an
 * upload. The server still re-validates; this is a convenience, not security.
 * Extension is checked too because some browsers report an empty MIME type.
 */
export function validateResumeFile(file: File): ApiError | null {
  const extOk = /\.(pdf|docx)$/i.test(file.name);
  const typeOk = file.type === "" || ALLOWED_TYPES.has(file.type);
  if (!extOk || !typeOk) return new ApiError("unsupported_file_type", "Only PDF and DOCX files are supported.", 415);
  if (file.size > MAX_RESUME_BYTES) return new ApiError("file_too_large", "That file is over 5 MB.", 413);
  if (file.size === 0) return new ApiError("validation_failed", "That file is empty.", 422);
  return null;
}
