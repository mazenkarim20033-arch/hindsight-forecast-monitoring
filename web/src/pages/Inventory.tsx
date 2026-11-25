import { useState } from "react";
import { api } from "../api/client";
import type { Inventory as Result, InventoryInputs, ScenarioSpec, StrategyKey } from "../api/types";
import { HealthCaution } from "../components/HealthNote";
import Num from "../components/Num";
import RecordDecision from "../components/RecordDecision";
import { ErrorBox, Loading } from "../components/States";
import { useAsync } from "../hooks/useAsync";
import { useLang, useServerText } from "../i18n";
import { num, pct } from "../lib/format";
import { useSession } from "../state/session";
import { useBaseInputs, useDebounced, type BaseInputs } from "./baseInputs";
import Planner, { Meter } from "./Planner";
import Scenarios from "./Scenarios";

const STRATEGIES: StrategyKey[] = ["conservative", "balanced", "high_availability"];

export default function Inventory() {
  const { t } = useLang();
  const [view, setView] = useState<"orders" | "scenarios" | "backtest">("orders");
  const base = useBaseInputs();
  return (
    <>
      <header className="page-head">
        <h1>{t("inv.title")}</h1>
        <p className="lede">{t("inv.lede")}</p>
      </header>
      {view !== "orders" && <p><button className="btn link" onClick={() => setView("orders")}>{t("inv.back")}</button></p>}
      {view === "orders" ? <Orders base={base} openTool={setView} /> : view === "scenarios" ? <Scenarios base={base} goOrders={() => setView("orders")} /> : <Planner />}
    </>
  );
}

const risk = (p: number): "low" | "medium" | "high" => (p < 0.1 ? "low" : p < 0.25 ? "medium" : "high");
const OPTION_KEYS: StrategyKey[] = ["conservative", "balanced", "high_availability"];
const SHOWN = 10;

function downloadCsv(rows: string[][]) {
  const cell = (v: string) => (/[",\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v);
  const url = URL.createObjectURL(new Blob([rows.map((r) => r.map(cell).join(",")).join("\n")], { type: "text/csv" }));
  const a = document.createElement("a");
  a.href = url; a.download = "order-list.csv"; a.click();
  URL.revokeObjectURL(url);
}

type Change = "up" | "down" | "late" | "stock";
const CHANGES: Record<Change, { name: string; spec: Omit<ScenarioSpec, "name">; recorded: string | null }> = {
  up: { name: "Sales go up 20%", spec: { demand_change_pct: 20 }, recorded: "Demand up 20%" },
  down: { name: "Sales go down 20%", spec: { demand_change_pct: -20 }, recorded: null },
  late: { name: "Delivery is 5 days late", spec: { supplier_delay_days: 5 }, recorded: "Supplier 5 days late" },
  stock: { name: "I have 30% less stock", spec: { stock_reduction_pct: 30 }, recorded: "Stock 30% lower" },
};

/** "What if something changes?": four buttons, one plain sentence each. The full scenario builder stays one click away for people who want it. */
function QuickWhatIf({ body, strategy, locked, advanced }: { body: InventoryInputs; strategy: StrategyKey; locked: boolean; advanced: () => void }) {
  const { dataset } = useSession();
  const { t } = useLang();
  const say = useServerText();
  const [pick, setPick] = useState<Change | null>(null);
  const key = JSON.stringify({ body, pick });
  const res = useAsync((signal) => (pick ? api.scenarios(dataset!.id, { ...body, scenarios: [{ name: CHANGES[pick].name, ...CHANGES[pick].spec }] }, signal) : Promise.resolve(null)), [dataset!.id, key]);
  const run = res.data;
  const s = run && pick ? (locked ? run.scenarios.find((x) => x.name === CHANGES[pick].recorded) : run.scenarios[0]) : null;
  const order = s?.comparison?.totals[strategy]?.order;
  const kept = s?.comparison?.if_baseline_order[strategy];
  const miss = kept ? (kept.expected_shortage.scenario ?? 0) - (kept.expected_shortage.baseline ?? 0) : 0;
  const unsold = kept ? (kept.expected_leftover.scenario ?? 0) - (kept.expected_leftover.baseline ?? 0) : 0;
  return (
    <section className="section">
      <h2>{t("inv.whatif.title")}</h2>
      <p className="muted">{t("inv.whatif.lede")}</p>
      <div className="toolbar" role="group" aria-label={t("inv.whatif.title")}>
        {(Object.keys(CHANGES) as Change[]).filter((k) => !locked || CHANGES[k].recorded).map((k) => (
          <button key={k} className={`btn ${pick === k ? "primary" : ""}`} aria-pressed={pick === k} onClick={() => setPick(pick === k ? null : k)}>{t(`inv.wi.${k}`)}</button>
        ))}
      </div>
      {pick && res.error && <ErrorBox problem={res.error} onRetry={res.reload} />}
      {pick && !run && !res.error && <Loading />}
      {pick && run && s && (
        <div className="whatif-answer" role="status">
          {s.error ? <p className="note-box">{say(s.error, "problem")}</p> : order && order.baseline != null && order.scenario != null ? (
            <>
              <p className="headline-sm">{t("inv.wi.order", { scenario: num(order.scenario), base: num(order.baseline), change: order.delta_pct == null ? "" : `${order.delta_pct > 0 ? "+" : order.delta_pct < 0 ? "−" : ""}${pct(Math.abs(order.delta_pct))}` })}</p>
              <p>{miss > 0.5 && miss >= unsold ? t("inv.wi.miss", { n: num(miss) }) : unsold > 0.5 ? t("inv.wi.left", { n: num(unsold) }) : t("inv.wi.same")}</p>
              <p className="fine">{t("inv.wi.note")}</p>
            </>
          ) : null}
        </div>
      )}
      {!locked && <p><button className="btn link" onClick={advanced}>{t("inv.wi.advanced")}</button></p>}
    </section>
  );
}

function Orders({ base, openTool }: { base: BaseInputs; openTool: (v: "scenarios" | "backtest") => void }) {
  const { dataset, overview } = useSession();
  const { t, n } = useLang();
  const { mode, setMode, form, set, stock, setStock, illustrative, guess, fillExample, clear, body, locked, hasFile, fromFile, fillFromFile } = base;
  const [strategy, setStrategy] = useState<StrategyKey>("balanced");
  const [query, setQuery] = useState("");
  const [all, setAll] = useState(false);
  const key = useDebounced(JSON.stringify(body));
  const res = useAsync((signal) => (key === "null" ? Promise.resolve(null) : api.inventory(dataset!.id, JSON.parse(key), signal)), [dataset!.id, key]);
  const r: Result | null = res.data;
  const ok = r ? r.items.filter((i) => i.status === "ok") : [];
  const total = r?.totals[strategy];
  // Without costs every item gets the same safety level, so every item has the same risk and the column says nothing: then it is hidden and the biggest orders come first.
  // With costs and stock the risk differs between items, and the items most likely to run out come first.
  const risks = r ? r.items.map((i) => i.by_strategy[strategy]?.p_stockout).filter((x): x is number => x !== undefined) : [];
  const varied = risks.length > 1 && Math.max(...risks) - Math.min(...risks) >= 0.02;
  const sorted = r ? [...r.items].sort((a, b) => (varied ? (b.by_strategy[strategy]?.p_stockout ?? -1) - (a.by_strategy[strategy]?.p_stockout ?? -1) : (b.by_strategy[strategy]?.order ?? -1) - (a.by_strategy[strategy]?.order ?? -1))) : [];
  const q = query.trim().toLowerCase();
  const matching = q ? sorted.filter((i) => i.item.toLowerCase().includes(q)) : sorted;
  const rows = all || q ? matching : matching.slice(0, SHOWN);

  return (
    <>
      <HealthCaution />
      {locked && <p className="note-box">{t("inv.snapshot")}</p>}
      {illustrative && <p className="note-box" role="note">{t("inv.illustrative")}</p>}

      <section className="section">
        <div className="toolbar" style={{ alignItems: "start" }}>
          {mode === "periodic_review" ? <Num label={t("inv.f.lead")} value={form.lead} onChange={set("lead")} disabled={locked} /> : <Num label={t("inv.f.period")} value={form.period} onChange={set("period")} disabled={locked} />}
        </div>
        {guess && !locked && <p className="note-box" role="note">{t("inv.guess", { lead: form.lead, review: form.review })}</p>}
      </section>

      {!body && <p className="note-box">{t("inv.hint")}</p>}
      {body && res.error && <ErrorBox problem={res.error} onRetry={res.reload} />}
      {body && !r && !res.error && <Loading />}

      {body && r && (
        <>
          <section className="section">
            <h2>{t("inv.answer.title")}</h2>
            {ok.length === 0 ? <p className="note-box">{t("inv.limited")}</p> : (
              <>
                <p className="headline-sm">{t("inv.answer2", { total: num(total?.order), count: n("unit.item", ok.length), days: n("unit.day", r.window_days) })}</p>
                <p className="muted">{t("inv.answer2.chance", { chance: pct(r.levels[strategy]) })}</p>
                {r.items.length > SHOWN && (
                  <label className="field" style={{ maxWidth: "20rem" }}><span>{t("inv.search")}</span><input type="search" value={query} onChange={(e) => setQuery(e.target.value)} /></label>
                )}
                <div className="table-wrap" tabIndex={0} role="region" aria-label={t("inv.list.title")}>
                  <table>
                    <thead><tr><th scope="col">{t("score.items.item")}</th><th scope="col" className="num">{t("inv.col.order_now")}</th><th scope="col" className="num">{t("inv.col.expected")}</th>{varied && <th scope="col">{t("inv.col.risk")}</th>}</tr></thead>
                    <tbody>
                      {rows.map((i) => {
                        const s = i.by_strategy[strategy];
                        return (
                          <tr key={i.item}>
                            <th scope="row">{i.item}</th>
                            {s ? (
                              <>
                                <td className="num"><strong>{num(s.order)}</strong></td>
                                <td className="num">{num(i.forecast_demand)}</td>
                                {varied && <td><span className={`risk ${risk(s.p_stockout)}`}>{t(`inv.risk.${risk(s.p_stockout)}`)}</span> <small className="muted">{pct(s.p_stockout)}</small></td>}
                              </>
                            ) : <td colSpan={varied ? 3 : 2}>{t("inv.limited.item")}</td>}
                          </tr>
                        );
                      })}
                      {rows.length === 0 && <tr><td colSpan={varied ? 4 : 3}>{t("inv.search.none")}</td></tr>}
                    </tbody>
                  </table>
                </div>
                <p className="toolbar">
                  {!q && matching.length > SHOWN && <button className="btn" onClick={() => setAll(!all)}>{all ? t("inv.show_less") : t("inv.show_all", { n: matching.length })}</button>}
                  <button className="btn" onClick={() => downloadCsv([["item", "order_now", "expected_sales", "risk_of_running_out"], ...sorted.filter((i) => i.by_strategy[strategy]).map((i) => [i.item, String(i.by_strategy[strategy]!.order), String(i.forecast_demand), String(i.by_strategy[strategy]!.p_stockout)])])}>{t("inv.csv")}</button>
                </p>
                <p className="fine">{t("inv.answer.note")}</p>
              </>
            )}
          </section>
          {ok.length > 0 && <QuickWhatIf body={body} strategy={strategy} locked={locked} advanced={() => openTool("scenarios")} />}
        </>
      )}

      <details className="more">
        <summary>{t("inv.settings")}</summary>
        <div className="toolbar" style={{ alignItems: "start" }}>
          {mode === "periodic_review" && <Num label={t("inv.f.review")} value={form.review} onChange={set("review")} disabled={locked} placeholder="7" />}
        </div>
        <fieldset className="plain-fieldset">
          <legend>{t("inv.care")}</legend>
          <div className="seg" role="radiogroup" aria-label={t("inv.care")}>
            {OPTION_KEYS.map((k) => (
              <label key={k} className={k === strategy ? "on" : ""}><input type="radio" name="inv-option" checked={k === strategy} onChange={() => setStrategy(k)} />{t(`inv.opt.${k}`)}</label>
            ))}
          </div>
          <p className="fine">{t(`inv.opt.${strategy}.desc`)}</p>
        </fieldset>
        {!locked && (
          <p>
            {hasFile && <><button className="btn primary" onClick={fillFromFile}>{t("inv.fromfile")}</button>{" "}</>}
            <button className="btn" onClick={fillExample}>{t("inv.example")}</button>{" "}
            <button className="btn link" onClick={clear}>{t("inv.clear")}</button>
          </p>
        )}
        {fromFile && <p className="note-box" role="note">{t("inv.fromfile.note", { items: fromFile.items, price: t(`inv.fromfile.${fromFile.price}`, { what: t("inv.f.price") }), cost: t(`inv.fromfile.${fromFile.cost}`, { what: t("inv.f.cost") }) })}</p>}
        <h3>{t("inv.more.details")}</h3>
        <p className="fine">{t("inv.more.costs.lede")}</p>
        <div className="seg" role="radiogroup" aria-label={t("inv.mode")} style={{ marginBottom: "0.8rem" }}>
          {(["periodic_review", "single_period"] as const).map((m) => (
            <label key={m} className={mode === m ? "on" : ""}><input type="radio" name="inv-mode" checked={mode === m} disabled={locked} onChange={() => setMode(m)} />{t(`inv.mode.${m}`)}</label>
          ))}
        </div>
        <div className="toolbar" style={{ alignItems: "start" }}>
          {mode === "single_period" && <Num label={t("inv.f.salvage")} value={form.salvage} onChange={set("salvage")} disabled={locked} />}
          <Num label={t("inv.f.price")} value={form.price} onChange={set("price")} disabled={locked} />
          <Num label={t("inv.f.cost")} value={form.cost} onChange={set("cost")} disabled={locked} />
          <Num label={t("inv.f.holding")} value={form.holding} onChange={set("holding")} disabled={locked} />
          <Num label={t("inv.f.penalty")} value={form.penalty} onChange={set("penalty")} disabled={locked} />
          <Num label={t("inv.f.service")} value={form.service} onChange={set("service")} disabled={locked} placeholder="95" />
          <Num label={t("inv.f.moq")} value={form.moq} onChange={set("moq")} disabled={locked} />
          <Num label={t("inv.f.multiple")} value={form.multiple} onChange={set("multiple")} disabled={locked} />
        </div>
        <h3>{t("inv.more.stock")}</h3>
        <p className="muted">{t("inv.stock.lede")}</p>
        <div className="table-wrap" tabIndex={0} role="region" aria-label={t("inv.stock")}>
          <table>
            <thead><tr><th scope="col">{t("score.items.item")}</th><th scope="col">{t("inv.col.onhand")}</th><th scope="col">{t("inv.col.onorder")}</th></tr></thead>
            <tbody>
              {(overview?.series ?? []).map((s) => (
                <tr key={s.id}>
                  <th scope="row">{s.id}</th>
                  {(["on_hand", "on_order"] as const).map((f) => (
                    <td key={f}>
                      <input className="cell" type="text" inputMode="decimal" disabled={locked} aria-label={`${s.id}: ${t(f === "on_hand" ? "inv.col.onhand" : "inv.col.onorder")}`}
                        value={stock[s.id]?.[f] ?? ""} onChange={(e) => { const v = e.target.value; setStock((x) => ({ ...x, [s.id]: { ...(x[s.id] ?? { on_hand: "", on_order: "" }), [f]: v } })); }} />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {body && r && !locked && ok.length > 0 && (
          <>
            <h3>{t("inv.record.title")}</h3>
            <RecordDecision body={body} items={r.items} strategy={strategy} />
          </>
        )}
        {body && r && (
          <>
            <h3>{t("inv.details")}</h3>
            <Results r={r} strategy={strategy} setStrategy={setStrategy} n={n} />
          </>
        )}
        <p><button className="btn" onClick={() => openTool("backtest")}>{t("inv.tools.backtest")}</button></p>
      </details>
    </>
  );
}

function Results({ r, strategy, setStrategy, n }: { r: Result; strategy: StrategyKey; setStrategy: (s: StrategyKey) => void; n: (k: string, c: number) => string }) {
  const { t } = useLang();
  const ok = r.items.filter((i) => i.status === "ok");
  const money = (x: number | null | undefined) => (x == null ? "–" : num(x, 0));
  return (
    <>
      <section className="section">
        <div className="section-head"><h2 id="inv-cmp">{t("inv.compare")}</h2><span className="chip prediction">{t("chip.forecast")}</span></div>
        <p className="muted">{t("inv.cover", { days: n("unit.day", r.window_days) })}</p>
        {!r.cost_based && <p className="note-box">{t("inv.note.no_costs")} {r.missing.length > 0 && t("inv.missing", { list: r.missing.map((m) => t(`inv.a.${m}`)).join(", ") })}</p>}
        {ok.length === 0 ? <p className="note-box">{t("inv.limited")}</p> : (
          <div className="table-wrap" tabIndex={0} role="region" aria-label={t("inv.compare")}>
            <table>
              <thead>
                <tr>
                  <th scope="col">{t("inv.strategy")}</th>
                  <th scope="col">{t("inv.c.target")}</th>
                  <th scope="col" className="num">{t("inv.c.order")}</th>
                  <th scope="col" className="num">{t("inv.c.invest")}</th>
                  <th scope="col" className="num">{t("inv.c.left")}</th>
                  <th scope="col" className="num">{t("inv.c.short")}</th>
                  <th scope="col" className="num">{t("inv.c.cost")}</th>
                </tr>
              </thead>
              <tbody>
                {STRATEGIES.map((k) => {
                  const tt = r.totals[k];
                  return (
                    <tr key={k} className={k === strategy ? "on" : ""}>
                      <th scope="row"><button className="btn link" aria-pressed={k === strategy} onClick={() => setStrategy(k)}>{t(`inv.strategy.${k}`)}</button></th>
                      <td><Meter value={r.levels[k]} tone="left" /></td>
                      <td className="num">{num(tt?.order)}</td>
                      <td className="num">{money(tt?.investment)}</td>
                      <td className="num">{num(tt?.expected_leftover)}</td>
                      <td className="num">{num(tt?.expected_shortage)}</td>
                      <td className="num">{money(tt?.expected_cost)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        <p className="fine">{t(`inv.strategy.${strategy}.desc`)}</p>
      </section>

      {ok.length > 0 && (
        <section className="section">
          <div className="section-head"><h2 id="inv-items">{t("inv.items", { strategy: t(`inv.strategy.${strategy}`) })}</h2></div>
          <div className="table-wrap" tabIndex={0} role="region" aria-label={t("inv.items", { strategy: t(`inv.strategy.${strategy}`) })}>
            <table>
              <thead>
                <tr>
                  <th scope="col">{t("score.items.item")}</th>
                  <th scope="col" className="num">{t("inv.c.forecast")}</th>
                  <th scope="col" className="num">{t("inv.c.position")}</th>
                  <th scope="col" className="num">{t("inv.c.rec")}</th>
                  <th scope="col" className="num">{t("inv.c.left")}</th>
                  <th scope="col">{t("inv.c.risk")}</th>
                  <th scope="col" className="num">{t("inv.c.excess")}</th>
                  <th scope="col" className="num">{t("inv.c.lost")}</th>
                </tr>
              </thead>
              <tbody>
                {r.items.map((i) => {
                  const s = i.by_strategy[strategy];
                  return (
                    <tr key={i.item}>
                      <th scope="row">{i.item}{i.flags.map((f) => <small key={f} className="muted" style={{ display: "block" }}>{t(`inv.flag.${f}`)}</small>)}</th>
                      <td className="num">{num(i.forecast_demand)}</td>
                      <td className="num">{i.inventory_position == null ? "–" : num(i.inventory_position)}</td>
                      {s ? (
                        <>
                          <td className="num"><strong>{num(s.order)}</strong></td>
                          <td className="num">{num(s.expected_leftover, 1)}</td>
                          <td><Meter value={s.p_stockout} tone="short" /></td>
                          <td className="num">{money(s.expected_excess_cost)}</td>
                          <td className="num">{money(s.expected_stockout_cost)}</td>
                        </>
                      ) : <td colSpan={5}>{t("inv.limited.item")}</td>}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <section className="section">
        <div className="section-head"><h2 id="inv-as">{t("inv.assumptions")}</h2></div>
        <ul className="plain">
          {r.assumptions.map((a) => (
            <li key={a.field}>{t(`inv.a.${a.field}`)}: <strong>{typeof a.value !== "number" ? a.value : ["service_level", "level_conservative", "level_balanced"].includes(a.field) ? pct(a.value) : num(a.value, Number.isInteger(a.value) ? 0 : 2)}</strong> <span className="muted">({t(`inv.src.${a.source}`)})</span></li>
          ))}
        </ul>
      </section>

      {r.calibration.length > 0 && (
        <section className="section">
          <div className="section-head"><h2 id="inv-cal">{t("inv.cal")}</h2><span className="chip evaluation">{t("chip.evaluation")}</span></div>
          <div className="table-wrap" tabIndex={0} role="region" aria-label={t("inv.cal")}>
            <table>
              <thead><tr><th scope="col">{t("inv.strategy")}</th><th scope="col" className="num">{t("inv.cal.target")}</th><th scope="col" className="num">{t("inv.cal.held")}</th><th scope="col" className="num">{t("inv.cal.cases")}</th></tr></thead>
              <tbody>
                {r.calibration.map((c) => (
                  <tr key={c.strategy}><th scope="row">{t(`inv.strategy.${c.strategy}`)}</th><td className="num">{pct(c.target, 1)}</td><td className="num">{pct(c.realized, 1)}</td><td className="num">{num(c.n_cases)}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="fine">{t("inv.cal.note")}</p>
        </section>
      )}

      <section className="section" aria-label={t("inv.limits")}>
        <ul className="plain">{r.notes.map((c) => <li key={c} className="fine">{t(`inv.note.${c}`)}</li>)}</ul>
      </section>
    </>
  );
}
