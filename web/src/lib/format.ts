/** "3 days ago" style relative time. Intl.RelativeTimeFormat handles locale and pluralisation. */
export function timeAgo(iso: string | null, now = Date.now()): string {
  if (!iso) return "";
  const seconds = Math.round((Date.parse(iso) - now) / 1000);
  const rtf = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
  const units: [Intl.RelativeTimeFormatUnit, number][] = [["day", 86400], ["hour", 3600], ["minute", 60]];
  for (const [unit, size] of units) {
    if (Math.abs(seconds) >= size) return rtf.format(Math.round(seconds / size), unit);
  }
  return "just now";
}

/** "2023-07" -> "Jul 2023"; null -> "Present". */
export function formatMonth(value: string | null): string {
  if (!value) return "Present";
  const [y, m] = value.split("-");
  if (!m) return y ?? value;
  return new Date(Date.UTC(Number(y), Number(m) - 1, 1)).toLocaleDateString("en", { month: "short", year: "numeric", timeZone: "UTC" });
}
