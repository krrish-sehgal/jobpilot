/**
 * True only for absolute http(s) URLs. Use before rendering any server- or
 * model-provided URL as a link: `javascript:`, `data:` and the like must never
 * reach an href.
 */
export function isSafeExternalUrl(value: string): boolean {
  try {
    const { protocol } = new URL(value);
    return protocol === "https:" || protocol === "http:";
  } catch {
    return false; // not an absolute URL at all
  }
}
