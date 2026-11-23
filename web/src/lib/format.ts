const LOCALE = "en-GB";

export function pct(x: number | null | undefined, digits = 0): string {
  return x == null || !Number.isFinite(x) ? "n/a" : `${(x * 100).toFixed(digits)}%`;
}

export function signedPoints(x: number, digits = 1): string {
  const v = (x * 100).toFixed(digits);
  return `${x > 0 ? "+" : x < 0 ? "−" : ""}${v.replace("-", "")} pts`;
}

export function num(x: number | null | undefined, digits = 0): string {
  return x == null || !Number.isFinite(x) ? "n/a" : x.toLocaleString(LOCALE, { maximumFractionDigits: digits, minimumFractionDigits: digits });
}

/** Parse "2024-03-15" as a local calendar day, so time zones never shift it. */
export function day(iso: string): Date {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d);
}

export function dateLong(iso: string): string {
  return day(iso).toLocaleDateString(LOCALE, { weekday: "short", day: "numeric", month: "short", year: "numeric" });
}

export function dateShort(iso: string): string {
  return day(iso).toLocaleDateString(LOCALE, { day: "numeric", month: "short" });
}

export function monthYear(iso: string): string {
  return day(iso).toLocaleDateString(LOCALE, { month: "short", year: "2-digit" });
}

export function addDays(iso: string, n: number): string {
  const d = day(iso);
  d.setDate(d.getDate() + n);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export function plural(n: number, one: string, many = `${one}s`): string {
  return `${num(n)} ${n === 1 ? one : many}`;
}
