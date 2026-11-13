/**
 * UUID v4 via the Web Crypto API. Used for `client_message_id`, which makes
 * message posts idempotent: retrying with the same id never creates a second
 * agent turn. Falls back to Math.random only where crypto.randomUUID is
 * unavailable (very old browsers, or non-secure http contexts in dev).
 */
export function uuid(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
  });
}
