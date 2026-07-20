/** Date helpers — ISO8601 formatting, trading-day string validation. */

/** Returns the current time as ISO8601 (UTC, second precision). */
export function nowIso(): string {
  return new Date().toISOString().replace(/\.\d{3}Z$/, "Z")
}

/** True if s looks like an A-share trading date in YYYY-MM-DD form. */
export function isTradingDate(s: string): boolean {
  return /^\d{4}-\d{2}-\d{2}$/.test(s)
}

/** Convert YYYYMMDD to YYYY-MM-DD (or return input if already dashed). */
export function normalizeDate(s: string): string {
  if (s.includes("-")) return s
  return `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6, 8)}`
}
