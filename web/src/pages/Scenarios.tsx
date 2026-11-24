import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import type { InventoryInputs, Pair, ScenarioResult, ScenarioRun, ScenarioSpec, StrategyKey } from "../api/types";
import Num from "../components/Num";
import RecordDecision from "../components/RecordDecision";
import { ErrorBox, Loading } from "../components/States";
import { useAsync } from "../hooks/useAsync";
import { useLang, useServerText } from "../i18n";
import { num, pct } from "../lib/format";
import { useSession } from "../state/session";
import { toNum, useDebounced, type BaseInputs } from "./baseInputs";

const STRATEGIES: StrategyKey[] = ["conservative", "balanced", "high_availability"];
const MAX_SCENARIOS = 8;
const STORE = "hindsight.scenarios.v1";

type Fields = "demand" | "promoPct" | "promoDays" | "seasonPct" | "seasonDays" | "spikePct" | "spikeDays" | "delay" | "stockCut" | "pricePct" | "elasticity";
interface Draft { id: string; name: string; include: boolean; f: Record<Fields, string> }
const BLANK: Record<Fields, string> = { demand: "", promoPct: "", promoDays: "", seasonPct: "", seasonDays: "", spikePct: "", spikeDays: "", delay: "", stockCut: "", pricePct: "", elasticity: "" };
type Preset = "blank" | "demand" | "delay" | "stock" | "price";
/** Starting points only. Each value is a guess the user is expected to change; none comes from the data. The price preset leaves the elasticity empty on purpose. */
const PRESETS: Record<Preset, Partial<Record<Fields, string>>> = { blank: {}, demand: { demand: "20" }, delay: { delay: "5" }, stock: { stockCut: "30" }, price: { pricePct: "-10" } };

let counter = 0;
const newId = () => `s${Date.now().toString(36)}${counter++}`;

function load(): Draft[] {
  try {
    const raw = JSON.parse(localStorage.getItem(STORE) ?? "[]");
    return Array.isArray(raw) ? raw.filter((d) => d && typeof d.id === "string" && typeof d.name === "string" && d.f).map((d) => ({ ...d, f: { ...BLANK, ...d.f } })).slice(0, MAX_SCENARIOS) : [];
  } catch { return []; }
}

function toSpec(d: Draft): ScenarioSpec {
  const f = d.f;
  const s: ScenarioSpec = { name: d.name.trim() || "Scenario" };
  const put = <K extends keyof ScenarioSpec>(k: K, v: string) => { const x = toNum(v); if (x !== undefined) (s as unknown as Record<string, unknown>)[k] = x; };
  put("demand_change_pct", f.demand); put("promo_uplift_pct", f.promoPct); put("promo_days", f.promoDays); put("seasonal_change_pct", f.seasonPct); put("seasonal_days", f.seasonDays);
  put("spike_pct", f.spikePct); put("spike_days", f.spikeDays); put("supplier_delay_days", f.delay); put("stock_reduction_pct", f.stockCut); put("price_change_pct", f.pricePct); put("price_elasticity", f.elasticity);
  return s;
}

const signed = (x: number, digits = 1) => `${x > 0 ? "+" : x < 0 ? "−" : ""}${num(Math.abs(x), digits)}`;

function download(name: string, text: string, type: string) {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = document.createElement("a");
  a.href = url; a.download = name; a.click();
  URL.revokeObjectURL(url);
}

export default function Scenarios({ base, goOrders }: { base: BaseInputs; goOrders: () => void }) {
  const { dataset } = useSession();
  const { t } = useLang();
  const locked = base.locked;
  const [drafts, setDrafts] = useState<Draft[]>(load);
  const [strategy, setStrategy] = useState<StrategyKey>("balanced");
  const [detail, setDetail] = useState(0);
  useEffect(() => { try { localStorage.setItem(STORE, JSON.stringify(drafts)); } catch { /* storage may be blocked: scenarios then last until the page closes */ } }, [drafts]);

  const patch = (id: string, fn: (d: Draft) => Draft) => setDrafts((l) => l.map((d) => (d.id === id ? fn(d) : d)));
  const add = (p: Preset) => setDrafts((l) => l.length >= MAX_SCENARIOS ? l : [...l, { id: newId(), name: t(`scn.preset.${p}`), include: true, f: { ...BLANK, ...PRESETS[p] } }]);

  const specs = useMemo(() => drafts.filter((d) => d.include).map(toSpec), [drafts]);
  const body = base.body && (locked || specs.length > 0) ? { ...base.body, scenarios: specs } : null;
  const key = useDebounced(JSON.stringify(body));
  const res = useAsync((signal) => (key === "null" ? Promise.resolve(null) : api.scenarios(dataset!.id, JSON.parse(key), signal)), [dataset!.id, key]);
  const run: ScenarioRun | null = res.data;

  return (
    <>
      <p className="note-box" role="note">{t("scn.hypothetical")}</p>
      {locked && <p className="note-box">{t("scn.snapshot")}</p>}
      <section className="section">
        <div className="section-head"><h2>{t("scn.baseline")}</h2><span className="chip dataset">{t("chip.assumption")}</span></div>
        <p className="muted">{t("scn.baseline.lede")} {base.body ? "" : t("scn.baseline.none")}</p>
        {!locked && <p><button className="btn" onClick={goOrders}>{t("scn.baseline.edit")}</button></p>}
      </section>

      {!locked && (
        <section className="section">
          <div className="section-head"><h2>{t("scn.yours")}</h2><span className="chip dataset">{t("chip.assumption")}</span></div>
          <p className="muted">{t("scn.yours.lede")}</p>
          <p className="toolbar">
            {(["blank", "demand", "delay", "stock", "price"] as const).map((p) => <button key={p} className="btn" disabled={drafts.length >= MAX_SCENARIOS} onClick={() => add(p)}>{t(`scn.add.${p}`)}</button>)}
            {drafts.length > 0 && <button className="btn link" onClick={() => setDrafts([])}>{t("scn.reset")}</button>}
          </p>
          {drafts.length === 0 && <p className="note-box">{t("scn.empty")}</p>}
          {drafts.map((d) => (
            <fieldset key={d.id} className="field-group" style={{ marginBottom: "1rem" }}>
              <legend>{d.name || t("scn.unnamed")}</legend>
              <div className="toolbar" style={{ alignItems: "end" }}>
                <Num label={t("scn.name")} value={d.name} onChange={(v) => patch(d.id, (x) => ({ ...x, name: v }))} />
                <label className="field"><span>{t("scn.include")}</span><input type="checkbox" checked={d.include} onChange={(e) => patch(d.id, (x) => ({ ...x, include: e.target.checked }))} /></label>
                <button className="btn link" onClick={() => setDrafts((l) => l.filter((x) => x.id !== d.id))}>{t("scn.remove")}</button>
              </div>
              <div className="toolbar" style={{ alignItems: "start" }}>
                {([["demand", "scn.f.demand"], ["promoPct", "scn.f.promoPct"], ["promoDays", "scn.f.promoDays"], ["seasonPct", "scn.f.seasonPct"], ["seasonDays", "scn.f.seasonDays"],
                  ["spikePct", "scn.f.spikePct"], ["spikeDays", "scn.f.spikeDays"], ["delay", "scn.f.delay"], ["stockCut", "scn.f.stockCut"], ["pricePct", "scn.f.pricePct"], ["elasticity", "scn.f.elasticity"]] as const)
                  .map(([f, label]) => <Num key={f} label={t(label)} value={d.f[f]} onChange={(v) => patch(d.id, (x) => ({ ...x, f: { ...x.f, [f]: v } }))} />)}
              </div>
            </fieldset>
          ))}
        </section>
      )}

      {!body && base.body == null && <p className="note-box">{t("scn.hint.baseline")}</p>}
      {!body && base.body != null && !locked && drafts.length > 0 && <p className="note-box">{t("scn.hint.include")}</p>}
      {body && res.error && <ErrorBox problem={res.error} onRetry={res.reload} />}
      {body && !run && !res.error && <Loading />}
      {body && run && <Results run={run} strategy={strategy} setStrategy={setStrategy} detail={Math.min(detail, Math.max(run.scenarios.length - 1, 0))} setDetail={setDetail} baseBody={locked ? null : base.body} />}
    </>
  );
}

function Delta({ p, digits = 0 }: { p: Pair; digits?: number }) {
  const shown = p.scenario;
  return (
    <td className="num">
      {shown == null ? "–" : num(shown, digits)}
      {p.delta != null && Math.abs(p.delta) >= 0.005 && <small className="muted" style={{ display: "block" }}>{p.delta_pct != null && Math.abs(p.delta_pct) < 10 ? `${signed(p.delta_pct * 100)}%` : signed(p.delta, digits)}</small>}
    </td>
  );
}

function effectText(e: NonNullable<ScenarioResult["effects"]>[number], t: (k: string, p?: Record<string, string | number>) => string): string {
  const p = (k: string) => Number(e[k]);
  switch (e.kind) {
    case "demand_change": return t("scn.effect.demand_change", { pct: `${signed(p("pct"))}%` });
    case "promotion": case "seasonal": case "spike":
      return t(`scn.effect.${e.kind}`, { pct: `${signed(p("pct"))}%`, days: p("days_applied"), window: p("window_days") }) + (p("days") > p("days_applied") ? ` ${t("scn.effect.cut", { asked: p("days") })}` : "");
    case "supplier_delay": return t("scn.effect.supplier_delay", { days: p("days"), lead: p("lead_time_days") });
    case "stock_reduction": return t("scn.effect.stock_reduction", { pct: num(p("pct"), 1) });
    case "price_change": return t("scn.effect.price_change", { pct: `${signed(p("pct"))}%`, price: num(p("price"), 2), elasticity: num(p("elasticity"), 2), factor: num(Number(e.demand_factor), 3) });
    default: return e.kind;
  }
}

function Results({ run, strategy, setStrategy, detail, setDetail, baseBody }: { run: ScenarioRun; strategy: StrategyKey; setStrategy: (s: StrategyKey) => void; detail: number; setDetail: (i: number) => void; baseBody: InventoryInputs | null }) {
  const { t } = useLang();
  const say = useServerText();
  const base = run.baseline;
  const bt = base.totals[strategy];
  const money = (x: number | null | undefined) => (x == null ? "–" : num(x, 0));
  const ok = run.scenarios.filter((s) => s.result);
  const sel = run.scenarios[detail];

  const exportCsv = () => {
    const head = ["scenario", "strategy", "total_order", "investment", "expected_leftover", "expected_shortage", "expected_cost", "baseline_order_kept_shortage", "baseline_order_kept_leftover", "baseline_order_kept_cost"];
    const rows = [["baseline", strategy, bt?.order, bt?.investment, bt?.expected_leftover, bt?.expected_shortage, bt?.expected_cost, "", "", ""]];
    for (const s of ok) {
      const tt = s.result!.totals[strategy], kept = s.comparison?.if_baseline_order[strategy];
      rows.push([s.name, strategy, tt?.order, tt?.investment, tt?.expected_leftover, tt?.expected_shortage, tt?.expected_cost, kept?.expected_shortage.scenario, kept?.expected_leftover.scenario, kept?.expected_cost.scenario]);
    }
    const cell = (v: unknown) => { const x = v == null ? "" : String(v); return /[",\n]/.test(x) ? `"${x.replace(/"/g, '""')}"` : x; };
    download("hindsight-scenarios.csv", [head, ...rows].map((r) => r.map(cell).join(",")).join("\n"), "text/csv");
  };

  return (
    <>
      <section className="section">
        <div className="section-head"><h2>{t("scn.compare")}</h2><span className="chip dataset">{t("chip.hypothetical")}</span></div>
        <div className="seg" role="radiogroup" aria-label={t("inv.strategy")} style={{ marginBottom: "0.8rem" }}>
          {STRATEGIES.map((k) => <label key={k} className={strategy === k ? "on" : ""}><input type="radio" name="scn-strategy" checked={strategy === k} onChange={() => setStrategy(k)} />{t(`inv.strategy.${k}`)}</label>)}
        </div>
        <p className="muted">{t("scn.cover", { base: base.window_days })}</p>
        <div className="table-wrap" tabIndex={0} role="region" aria-label={t("scn.compare")}>
          <table>
            <thead>
              <tr>
                <th scope="col">{t("scn.col.scenario")}</th>
                <th scope="col" className="num">{t("inv.c.order")}</th>
                <th scope="col" className="num">{t("inv.c.invest")}</th>
                <th scope="col" className="num">{t("inv.c.left")}</th>
                <th scope="col" className="num">{t("inv.c.short")}</th>
                <th scope="col" className="num">{t("inv.c.cost")}</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <th scope="row">{t("scn.baseline.row")}</th>
                <td className="num">{num(bt?.order)}</td><td className="num">{money(bt?.investment)}</td><td className="num">{num(bt?.expected_leftover)}</td><td className="num">{num(bt?.expected_shortage)}</td><td className="num">{money(bt?.expected_cost)}</td>
              </tr>
              {run.scenarios.map((s, i) => {
                const c = s.comparison?.totals[strategy];
                return s.error || !c ? (
                  <tr key={i}><th scope="row">{s.name}</th><td colSpan={5}>{s.error ? say(s.error, "problem") : t("inv.limited.item")}</td></tr>
                ) : (
                  <tr key={i}><th scope="row">{s.name}</th><Delta p={c.order} /><Delta p={c.investment} /><Delta p={c.expected_leftover} /><Delta p={c.expected_shortage} /><Delta p={c.expected_cost} /></tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p className="fine">{t("scn.compare.note")}</p>
        <p className="toolbar">
          <button className="btn" onClick={() => download("hindsight-scenarios.json", JSON.stringify(run, null, 2), "application/json")}>{t("scn.export.json")}</button>
          <button className="btn" onClick={exportCsv}>{t("scn.export.csv")}</button>
        </p>
      </section>

      {ok.length > 0 && (
        <section className="section">
          <div className="section-head"><h2>{t("scn.kept")}</h2><span className="chip prediction">{t("chip.forecast")}</span></div>
          <p className="muted">{t("scn.kept.lede")}</p>
          <div className="table-wrap" tabIndex={0} role="region" aria-label={t("scn.kept")}>
            <table>
              <thead>
                <tr><th scope="col">{t("scn.col.scenario")}</th><th scope="col" className="num">{t("inv.c.short")}</th><th scope="col" className="num">{t("inv.c.left")}</th><th scope="col" className="num">{t("inv.c.cost")}</th></tr>
              </thead>
              <tbody>
                <tr><th scope="row">{t("scn.baseline.row")}</th><td className="num">{num(bt?.expected_shortage)}</td><td className="num">{num(bt?.expected_leftover)}</td><td className="num">{money(bt?.expected_cost)}</td></tr>
                {ok.map((s, i) => {
                  const k = s.comparison?.if_baseline_order[strategy];
                  return k ? <tr key={i}><th scope="row">{s.name}</th><Delta p={k.expected_shortage} /><Delta p={k.expected_leftover} /><Delta p={k.expected_cost} /></tr> : null;
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <section className="section">
        <div className="section-head"><h2>{t("scn.assumptions")}</h2><span className="chip dataset">{t("chip.hypothetical")}</span></div>
        <ul className="plain">
          {run.scenarios.map((s, i) => (
            <li key={i}><strong>{s.name}</strong>
              {s.effects && s.effects.length > 0 ? <ul className="plain">{s.effects.map((e, j) => <li key={j}>{effectText(e, t)}</li>)}</ul> : <span className="muted"> {s.error ? "" : t("scn.noeffect")}</span>}
              {s.demand_factor != null && s.effects && s.effects.length > 0 && <span className="fine">{t("scn.factor", { factor: num(s.demand_factor, 3) })}</span>}
            </li>
          ))}
        </ul>
      </section>

      {ok.length > 0 && sel?.comparison && (
        <section className="section">
          <div className="section-head"><h2>{t("scn.items")}</h2></div>
          <label className="field" style={{ maxWidth: "24rem" }}>
            <span>{t("scn.col.scenario")}</span>
            <select value={detail} onChange={(e) => setDetail(Number(e.target.value))}>{run.scenarios.map((s, i) => <option key={i} value={i}>{s.name}</option>)}</select>
          </label>
          <div className="table-wrap" tabIndex={0} role="region" aria-label={t("scn.items")}>
            <table>
              <thead>
                <tr>
                  <th scope="col">{t("score.items.item")}</th>
                  <th scope="col" className="num">{t("scn.col.base_order")}</th>
                  <th scope="col" className="num">{t("scn.col.new_order")}</th>
                  <th scope="col" className="num">{t("scn.col.base_risk")}</th>
                  <th scope="col" className="num">{t("scn.col.kept_risk")}</th>
                </tr>
              </thead>
              <tbody>
                {sel.comparison.items.map((i) => {
                  const s = i.by_strategy?.[strategy];
                  return i.status === "ok" && s ? (
                    <tr key={i.item}>
                      <th scope="row">{i.item}</th>
                      <td className="num">{num(s.order.baseline)}</td><Delta p={s.order} />
                      <td className="num">{pct(s.p_stockout.baseline)}</td><td className="num">{pct(s.if_baseline_order?.p_stockout)}</td>
                    </tr>
                  ) : <tr key={i.item}><th scope="row">{i.item}</th><td colSpan={4}>{t("inv.limited.item")}</td></tr>;
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {baseBody && sel?.result && !sel.error && <RecordDecision body={baseBody} items={sel.result.items} strategy={strategy} scenario={{ name: sel.name, ...sel.spec }} />}

      <section className="section" aria-label={t("inv.limits")}>
        <ul className="plain">{run.notes.map((c) => <li key={c} className="fine">{t(`scn.note.${c}`)}</li>)}</ul>
      </section>
    </>
  );
}
