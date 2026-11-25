import { useEffect, useMemo, useState } from "react";
import { IS_SNAPSHOT } from "../api/client";
import type { InventoryInputs } from "../api/types";
import { useSession } from "../state/session";

export type Form = Record<"lead" | "review" | "period" | "price" | "cost" | "holding" | "penalty" | "salvage" | "service" | "moq" | "multiple", string>;
export const EMPTY: Form = { lead: "", review: "", period: "", price: "", cost: "", holding: "", penalty: "", salvage: "", service: "", moq: "", multiple: "" };
/** An example only: it fills the form so the screen can be explored. It is not data from the file. */
export const EXAMPLE: Form = { ...EMPTY, lead: "3", review: "7", price: "10", cost: "6", holding: "0.05" };
/** What the form starts with, so the page can show an answer at once. The page says it is a guess until the person changes it. */
export const STARTER: Form = { ...EMPTY, lead: "3", review: "7" };
export const EXAMPLE_COVER_DAYS = 5; // example stock on hand: this many days of average sales

export const toNum = (s: string): number | undefined => {
  const v = Number(s.replace(",", ".").trim());
  return s.trim() === "" || !Number.isFinite(v) ? undefined : v;
};

/** The business inputs shared by the order decisions and the what-if scenarios. Held by the page so switching tabs keeps them. */
export function useBaseInputs() {
  const { overview, method, dataset } = useSession();
  const [mode, setMode] = useState<InventoryInputs["mode"]>("periodic_review");
  const [form, setForm] = useState<Form>(IS_SNAPSHOT ? EXAMPLE : STARTER);
  const [guess, setGuess] = useState(!IS_SNAPSHOT);
  const avg = useMemo(() => Object.fromEntries((overview?.series ?? []).map((s) => [s.id, s.average_per_day])), [overview]);
  const exampleStock = () => Object.fromEntries(Object.entries(avg).map(([id, a]) => [id, { on_hand: String(Math.round(a * EXAMPLE_COVER_DAYS)), on_order: "0" }]));
  const [stock, setStock] = useState<Record<string, { on_hand: string; on_order: string }>>(() => (IS_SNAPSHOT ? exampleStock() : {}));
  const [illustrative, setIllustrative] = useState(IS_SNAPSHOT);
  const set = (k: keyof Form) => (v: string) => { setForm((f) => ({ ...f, [k]: v })); setGuess(false); };
  const fillExample = () => { setMode("periodic_review"); setForm(EXAMPLE); setStock(exampleStock()); setIllustrative(true); setGuess(false); };
  const fileValues = dataset?.report.business?.values ?? {};
  const hasFile = Object.keys(fileValues).length > 0;
  const [fromFile, setFromFile] = useState<{ items: number; price: "set" | "differs" | "none"; cost: "set" | "differs" | "none" } | null>(null);
  /** Stock per item comes from the file as it is. A price or cost is used only when every item has the same one, because the optimizer takes a single value. */
  const fillFromFile = () => {
    const ids = (overview?.series ?? []).map((x) => x.id);
    const nextStock: Record<string, { on_hand: string; on_order: string }> = {};
    for (const id of ids) {
      const v = fileValues[id];
      if (v?.on_hand !== undefined) nextStock[id] = { on_hand: String(v.on_hand), on_order: v.on_order !== undefined ? String(v.on_order) : "" };
    }
    const single = (k: "price" | "unit_cost"): { value?: number; state: "set" | "differs" | "none" } => {
      const vals = [...new Set(ids.map((id) => fileValues[id]?.[k]).filter((x): x is number => x !== undefined))];
      return vals.length === 0 ? { state: "none" } : vals.length === 1 ? { value: vals[0], state: "set" } : { state: "differs" };
    };
    const price = single("price"), cost = single("unit_cost");
    setStock(nextStock);
    setForm((f) => ({ ...f, price: price.value !== undefined ? String(price.value) : f.price, cost: cost.value !== undefined ? String(cost.value) : f.cost }));
    setIllustrative(false);
    setFromFile({ items: Object.keys(nextStock).length, price: price.state, cost: cost.state });
  };
  const clear = () => { setMode("periodic_review"); setForm(STARTER); setStock({}); setIllustrative(false); setFromFile(null); setGuess(true); };

  const body = useMemo<InventoryInputs | null>(() => {
    const ready = mode === "periodic_review" ? toNum(form.lead) !== undefined : toNum(form.period) !== undefined;
    if (!ready) return null;
    return {
      mode, method, lead_time_days: toNum(form.lead), review_days: toNum(form.review), period_days: toNum(form.period), price: toNum(form.price), unit_cost: toNum(form.cost),
      holding_cost_per_day: toNum(form.holding), stockout_penalty: toNum(form.penalty), salvage_value: toNum(form.salvage),
      service_level: toNum(form.service) === undefined ? undefined : toNum(form.service)! / 100, min_order_qty: toNum(form.moq), order_multiple: toNum(form.multiple),
      stock: Object.fromEntries(Object.entries(stock).map(([id, s]) => [id, { on_hand: toNum(s.on_hand), on_order: toNum(s.on_order) }]).filter(([, s]) => (s as { on_hand?: number }).on_hand !== undefined)),
    };
  }, [form, stock, mode, method]);
  return { mode, setMode, form, set, stock, setStock, illustrative, guess, fillExample, clear, body, locked: IS_SNAPSHOT, hasFile, fromFile, fillFromFile };
}
export type BaseInputs = ReturnType<typeof useBaseInputs>;

export function useDebounced<T>(value: T, ms = 400): T {
  const [v, setV] = useState(value);
  useEffect(() => { const id = setTimeout(() => setV(value), ms); return () => clearTimeout(id); }, [value, ms]);
  return v;
}
