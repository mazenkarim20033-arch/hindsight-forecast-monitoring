import { useState } from "react";
import { api } from "../api/client";
import type { Inventory as Result, StrategyKey } from "../api/types";
import { HealthCaution } from "../components/HealthNote";
import Num from "../components/Num";
import RecordDecision from "../components/RecordDecision";
import { ErrorBox, Loading } from "../components/States";
import { useAsync } from "../hooks/useAsync";
import { useLang } from "../i18n";
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

function Orders({ base, openTool }: { base: BaseInputs; openTool: (v: "scenarios" | "backtest") => void }) {
  const { dataset, overview } = useSession();
  const { t, n } = useLang();
  const { mode, setMode, form, set, stock, setStock, illustrative, fillExample, clear, body, locked, hasFile, fromFile, fillFromFile } = base;
  const [strategy, setStrategy] = useState<StrategyKey>("balanced");
  const key = useDebounced(JSON.stringify(body));
  const res = useAsync((signal) => (key === "null" ? Promise.resolve(null) : api.inventory(dataset!.id, JSON.parse(key), signal)), [dataset!.id, key]);
  const r: Result | null = res.data;
  const ok = r ? r.items.filter((i) => i.status === "ok") : [];
  const total = r?.totals[strategy];

  return (
    <>
      <HealthCaution />
      {locked && <p className="note-box">{t("inv.snapshot")}</p>}
      {illustrative && <p className="note-box" role="note">{t("inv.illustrative")}</p>}

      <section className="section">
        <h2>{t("inv.step.supply")}</h2>
        <div className="toolbar" style={{ alignItems: "start" }}>
          {mode === "periodic_review" ? (
            <>
              <Num label={t("inv.f.lead")} value={form.lead} onChange={set("lead")} disabled={locked} />
              <Num label={t("inv.f.review")} value={form.review} onChange={set("review")} disabled={locked} placeholder="7" />
            </>
          ) : (
            <Num label={t("inv.f.period")} value={form.period} onChange={set("period")} disabled={locked} />
          )}
        </div>
        {!locked && (
          <p>
            {hasFile && <><button className="btn primary" onClick={fillFromFile}>{t("inv.fromfile")}</button>{" "}</>}
            <button className="btn" onClick={fillExample}>{t("inv.example")}</button>{" "}
            <button className="btn link" onClick={clear}>{t("inv.clear")}</button>
          </p>
        )}
        {fromFile && <p className="note-box" role="note">{t("inv.fromfile.note", { items: fromFile.items, price: t(`inv.fromfile.${fromFile.price}`, { what: t("inv.f.price") }), cost: t(`inv.fromfile.${fromFile.cost}`, { what: t("inv.f.cost") }) })}</p>}

        <details className="more">
          <summary>{t("inv.more.costs")}</summary>
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
        </details>

        <details className="more">
          <summary>{t("inv.more.stock")}</summary>
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
        </details>
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
                <div className="options" role="radiogroup" aria-label={t("inv.strategy")}>
                  {OPTION_KEYS.map((k) => (
                    <label key={k} className={`option ${k === strategy ? "on" : ""}`}>
                      <input type="radio" name="inv-option" checked={k === strategy} onChange={() => setStrategy(k)} />
                      <strong>{t(`inv.opt.${k}`)}</strong>
                      <span className="option-big">{num(r.totals[k]?.order)}</span>
                      <span className="fine">{t(`inv.opt.${k}.desc`)}</span>
                    </label>
                  ))}
                </div>
                <p className="headline-sm">{t("inv.answer", { total: num(total?.order), count: n("unit.item", ok.length), days: n("unit.day", r.window_days), chance: pct(r.levels[strategy]) })}</p>
                <div className="table-wrap" tabIndex={0} role="region" aria-label={t("inv.answer.title")}>
                  <table>
                    <thead><tr><th scope="col">{t("score.items.item")}</th><th scope="col" className="num">{t("inv.col.order_now")}</th><th scope="col" className="num">{t("inv.c.forecast")}</th><th scope="col">{t("inv.col.risk")}</th></tr></thead>
                    <tbody>
                      {r.items.map((i) => {
                        const s = i.by_strategy[strategy];
                        return (
                          <tr key={i.item}>
                            <th scope="row">{i.item}</th>
                            {s ? (
                              <>
                                <td className="num"><strong>{num(s.order)}</strong></td>
                                <td className="num">{num(i.forecast_demand)}</td>
                                <td><span className={`risk ${risk(s.p_stockout)}`}>{t(`inv.risk.${risk(s.p_stockout)}`)}</span> <small className="muted">{pct(s.p_stockout)}</small></td>
                              </>
                            ) : <td colSpan={3}>{t("inv.limited.item")}</td>}
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
                <p className="fine">{t("inv.answer.note")}</p>
              </>
            )}
          </section>
          {!locked && ok.length > 0 && <RecordDecision body={body} items={r.items} strategy={strategy} />}
          <details className="more">
            <summary>{t("inv.details")}</summary>
            <Results r={r} strategy={strategy} setStrategy={setStrategy} n={n} />
          </details>
        </>
      )}

      <section className="section">
        <h2>{t("inv.tools")}</h2>
        <p className="toolbar">
          <button className="btn" onClick={() => openTool("scenarios")}>{t("inv.tools.scenarios")}</button>
          <button className="btn" onClick={() => openTool("backtest")}>{t("inv.tools.backtest")}</button>
        </p>
      </section>
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
