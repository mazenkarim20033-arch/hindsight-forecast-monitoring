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
/** What the things being tracked are called. Most files track products ("item"); a store or branch column says "store". */
export type Noun = "item" | "store";

/** Look up a message. A noun-specific wording (`key@store`) wins when the data tracks stores; falls back to English, then to the key itself. */
export function translate(lang: Lang, key: string, params?: Params, noun: Noun = "item"): string {
  const special = noun !== "item" ? `${key}@${noun}` : null;
  return fill((special && (DICT[lang][special] ?? en[special as Key])) || DICT[lang][key] || en[key as Key] || key, params);
}

/** From the header of the grouping column: store, branch, shop, location (or their Arabic names) mean stores; anything else means items. */
export function nounFor(header: string | null | undefined): Noun {
  return header && /(store|branch|shop|outlet|location|متجر|فرع|محل|معرض)/i.test(header) ? "store" : "item";
}

/** `unit.day` with n = 3 → "3 days" or "3 أيام", using the language's own plural rules. */
export function plural(lang: Lang, base: string, n: number, noun: Noun = "item"): string {
  const cat = new Intl.PluralRules(lang).select(n);
  const has = (k: string) => Boolean(DICT[lang][k] || (noun !== "item" && DICT[lang][`${k}@${noun}`]));
  return translate(lang, has(`${base}.${cat}`) ? `${base}.${cat}` : `${base}.other`, { n: n.toLocaleString(locale(lang)) }, noun);
}

export function locale(lang: Lang): string {
  return lang === "ar" ? "ar-EG-u-nu-latn" : "en-GB";
}

interface Ctx {
  lang: Lang;
  dir: "ltr" | "rtl";
  setLang: (l: Lang) => void;
  noun: Noun;
  setNoun: (n: Noun) => void;
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
  const [noun, setNoun] = useState<Noun>("item");
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
    lang, dir, setLang, noun, setNoun,
    t: (key, params) => translate(lang, key, params, noun),
    n: (key, count) => plural(lang, key, count, noun),
  }), [lang, dir, setLang, noun]);
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
