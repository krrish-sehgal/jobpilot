/**
 * One error type for everything the API layer can throw, so UI code only ever
 * has to handle `ApiError`. Codes mirror docs/web-api.md ("Errors") plus two
 * client-side ones: `network` (fetch itself failed) and `bad_response`
 * (the server answered, but not with the shape the contract promises).
 */
export type ApiErrorCode =
  | "unauthorized"
  | "not_found"
  | "validation_failed"
  | "rate_limited"
  | "resume_not_ready"
  | "file_too_large"
  | "unsupported_file_type"
  | "internal"
  | "network"
  | "bad_response";

export class ApiError extends Error {
  constructor(
    public readonly code: ApiErrorCode | (string & {}),
    message: string,
    public readonly status = 0,
    public readonly retryable = false,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export const isApiError = (e: unknown): e is ApiError => e instanceof ApiError;

/** Server-side problems and rate limits are worth retrying; the rest need the user to change something. */
export function isRetryableStatus(status: number): boolean {
  return status === 429 || status >= 500;
}

/** Friendly copy for the codes users can actually hit. Falls back to the server's own message. */
export function describeError(e: unknown): string {
  if (!isApiError(e)) return "Something went wrong. Please try again.";
  switch (e.code) {
    case "network":
      return "Can't reach JobPilot right now. Check your connection and try again.";
    case "rate_limited":
      return "You're going a little fast. Give it a few seconds and try again.";
    case "resume_not_ready":
      return "Your resume is still being parsed. Try again in a moment.";
    case "file_too_large":
      return "That file is over 5 MB. Try a smaller or compressed PDF.";
    case "unsupported_file_type":
      return "Only PDF and DOCX files are supported.";
    case "unauthorized":
      return "Your session expired. Please sign in again.";
    default:
      return e.message || "Something went wrong. Please try again.";
  }
}
