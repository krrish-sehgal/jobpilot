/**
 * Access-token storage.
 *
 * The token lives in a module variable (fast, never serialized) and is mirrored
 * to sessionStorage so a page refresh doesn't log you out, while closing the
 * tab does. sessionStorage gives a tab-scoped lifetime; it is equally exposed
 * to XSS as localStorage, so we rely on never injecting HTML (see lib/markdown.tsx).
 * We avoid cookies because we'd need CSRF protection.
 */
const KEY = "jobpilot.session";

interface StoredSession {
  token: string;
  expiresAt: string;
}

let memory: StoredSession | null = null;
const listeners = new Set<() => void>();

function readStorage(): StoredSession | null {
  try {
    const raw = sessionStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as StoredSession) : null;
  } catch {
    return null; // storage blocked or corrupted: behave as logged out
  }
}

export function getToken(): string | null {
  if (!memory && typeof window !== "undefined") memory = readStorage();
  if (memory && Date.parse(memory.expiresAt) <= Date.now()) {
    clearToken(false);
    return null;
  }
  return memory?.token ?? null;
}

/** When the stored token expires (epoch ms), or null if there is none. */
export function getExpiry(): number | null {
  if (!getToken() || !memory) return null;
  return Date.parse(memory.expiresAt);
}

export function setToken(token: string, expiresAt: string): void {
  memory = { token, expiresAt };
  try {
    sessionStorage.setItem(KEY, JSON.stringify(memory));
  } catch {
    /* in-memory only is still fine for this tab */
  }
}

/** `notify` is true when the server rejected us, so the AuthProvider can redirect to /login. */
export function clearToken(notify = true): void {
  memory = null;
  try {
    sessionStorage.removeItem(KEY);
  } catch {
    /* ignore */
  }
  if (notify) listeners.forEach((l) => l());
}

/** Subscribe to "the session was invalidated" (a 401 from any API call). */
export function onSessionLost(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
