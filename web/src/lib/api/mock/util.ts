import { uuid } from "@/lib/id";

/** Abortable sleep: mock streams must stop promptly when the user navigates away. */
export function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) return reject(new DOMException("Aborted", "AbortError"));
    const t = setTimeout(resolve, ms);
    signal?.addEventListener(
      "abort",
      () => {
        clearTimeout(t);
        reject(new DOMException("Aborted", "AbortError"));
      },
      { once: true },
    );
  });
}

export const nowIso = () => new Date().toISOString();
/** The real backend uses UUIDs for every id, so the mock does too. */
export const newId = (): string => uuid();
