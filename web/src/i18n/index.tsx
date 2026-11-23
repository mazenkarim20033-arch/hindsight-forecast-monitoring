import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { setFormatLanguage } from "../lib/format";
import { ar } from "./ar";
import { en, type Key } from "./en";

export type Lang = "en" | "ar";
type Params = Record<string, string | number>;
const DICT: Record<Lang, Record<string, string>> = { en, ar };
const STORE = "hindsight.lang";

function fill(s: string, p?: Params): string {
  return p ? s.replace(/\{(\w+)\}/g, (m, k) => (k in p ? String(p[k]) : m)) : s;
}

/** Look up a message. Falls back to English, then to the key itself, so a missing translation never breaks the page. */
export function translate(lang: Lang, key: string, params?: Params): string {
  return fill(DICT[lang][key] ?? en[key as Key] ?? key, params);
}

/** `unit.day` with n = 3 → "3 days" or "3 أيام", using the language's own plural rules. */
export function plural(lang: Lang, base: string, n: number): string {
  const cat = new Intl.PluralRules(lang).select(n);
  return translate(lang, DICT[lang][`${base}.${cat}`] ? `${base}.${cat}` : `${base}.other`, { n: n.toLocaleString(locale(lang)) });
}

export function locale(lang: Lang): string {
  return lang === "ar" ? "ar-EG-u-nu-latn" : "en-GB";
}

interface Ctx {
  lang: Lang;
  dir: "ltr" | "rtl";
  setLang: (l: Lang) => void;
  t: (key: Key | (string & {}), params?: Params) => string;
  n: (key: string, count: number) => string;
}
const LangCtx = createContext<Ctx | null>(null);

function initial(): Lang {
  try {
    const saved = localStorage.getItem(STORE);
    if (saved === "en" || saved === "ar") return saved;
  } catch { /* storage may be blocked */ }
  return typeof navigator !== "undefined" && navigator.language?.toLowerCase().startsWith("ar") ? "ar" : "en";
}

export function LangProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(initial);
  const dir = lang === "ar" ? "rtl" : "ltr";
  setFormatLanguage(lang); // idempotent; must happen before children format anything
  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = dir;
    document.title = lang === "ar" ? "Hindsight · إعادة عرض التوقعات" : "Hindsight";
  }, [lang, dir]);
  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    try { localStorage.setItem(STORE, l); } catch { /* ignore */ }
  }, []);
  const value = useMemo<Ctx>(() => ({
    lang, dir, setLang,
    t: (key, params) => translate(lang, key, params),
    n: (key, count) => plural(lang, key, count),
  }), [lang, dir, setLang]);
  return <LangCtx.Provider value={value}>{children}</LangCtx.Provider>;
}

export function useLang(): Ctx {
  const v = useContext(LangCtx);
  if (!v) throw new Error("useLang must be used inside LangProvider");
  return v;
}

/** Say a server message in the current language when it carries a known code, else show the server's own text. */
export function useServerText() {
  const { t, lang } = useLang();
  return useCallback((m: { text?: string; message?: string; code?: string; params?: Record<string, unknown> }, prefix: "note" | "problem" | "plan"): string => {
    const key = `${prefix}.${m.code}`;
    if (lang === "en" || !m.code || !(key in DICT[lang])) return m.text ?? m.message ?? "";
    const p: Params = {};
    for (const [k, v] of Object.entries(m.params ?? {})) p[k] = typeof v === "number" ? v.toLocaleString(locale(lang)) : String(v);
    return t(key, p);
  }, [t, lang]);
}
