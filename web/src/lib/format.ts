import { translate, type Lang } from "../i18n";

let LANG: Lang = "en";
let LOCALE = "en-GB";

/** Called by the language provider whenever the language changes, so every formatter below follows it. */
export function setFormatLanguage(lang: Lang) {
  LANG = lang;
  LOCALE = lang === "ar" ? "ar-EG-u-nu-latn" : "en-GB";
}

export function pct(x: number | null | undefined, digits = 0): string {
  return x == null || !Number.isFinite(x) ? "–" : `${(x * 100).toLocaleString(LOCALE, { minimumFractionDigits: digits, maximumFractionDigits: digits })}%`;
}

export function signedPoints(x: number, digits = 1): string {
  const v = Math.abs(x * 100).toLocaleString(LOCALE, { minimumFractionDigits: digits, maximumFractionDigits: digits });
  const sign = x > 0 ? "+" : x < 0 ? "−" : "";
  return translate(LANG, "pts", { v: `${sign}${v}` });
}

export function num(x: number | null | undefined, digits = 0): string {
  return x == null || !Number.isFinite(x) ? "–" : x.toLocaleString(LOCALE, { maximumFractionDigits: digits, minimumFractionDigits: digits });
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
