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
export const newId = (prefix: string) => `${prefix}-${Math.random().toString(36).slice(2, 10)}`;
