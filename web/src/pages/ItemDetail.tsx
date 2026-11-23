import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { NextView } from "../api/types";
import { ForecastChart } from "../components/ForecastChart";
import { Pickers, useMethodLabel } from "../components/Pickers";
import { ErrorBox, Loading } from "../components/States";
import { useAsync } from "../hooks/useAsync";
import { useLang } from "../i18n";
import { dateLong, dateShort, num, pct } from "../lib/format";
import { useSession } from "../state/session";

export default function ItemDetail() {
  const { id = "" } = useParams();
  const { dataset, overview, method, level } = useSession();
  const { t } = useLang();
  const [day, setDay] = useState(0);
  const item = decodeURIComponent(id);
  const next = useAsync((signal) => api.next(dataset!.id, { item, method, level, day }, signal), [dataset!.id, item, method, level, day]);
  const alerts = useAsync((signal) => api.alerts(dataset!.id, { method, item }, signal), [dataset!.id, item, method]);
  const dash = useAsync((signal) => api.dashboard(dataset!.id, { method }, signal), [dataset!.id, method]);
  const row = dash.data?.items.find((i) => i.id === item);
  const horizon = overview?.settings.horizon ?? 28;
  const n = next.data;
  return (
    <>
      <p className="crumbs"><Link to="/items">← {t("item.back")}</Link></p>
      <header className="page-head">
        <h1>{item}</h1>
        <p className="lede">{t("item.lede")}</p>
      </header>
      {overview && <Pickers overview={overview} />}
      {next.error && <ErrorBox problem={next.error} onRetry={next.reload} />}
      {!n && !next.error && <Loading text={t("next.loading")} />}
      {n && (
        <section className="section" aria-labelledby="fc-h">
          <div className="section-head"><h2 id="fc-h">{t("item.next.title", { n: horizon })}</h2><span className="chip prediction">{t("chip.forecast")}</span></div>
          <ForecastChart next={n} level={level} horizon={horizon} />
          <div className="two-col" style={{ marginTop: "1.25rem" }}>
            <div>
              <p className="muted">{t("next.expect", { total: num(n.total_next_7) })}{n.range_note ? ` ${t("next.range.none")}` : ""}</p>
              <div className="scroll short" role="region" aria-label={t("next.days.label")} tabIndex={0}>
                <table>
                  <thead><tr><th scope="col">{t("next.col.day")}</th><th scope="col" className="num">{t("next.col.guess")}</th><th scope="col" className="num">{t("next.col.range", { level: pct(level) })}</th></tr></thead>
                  <tbody>
                    {n.dates.map((d, i) => (
                      <tr key={d}>
                        <th scope="row">{dateLong(d)}</th>
                        <td className="num">{num(n.forecast[i])}</td>
                        <td className="num">{n.low[i] != null && n.high[i] != null ? t("score.to", { a: num(n.low[i]), b: num(n.high[i]) }) : "–"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
            <Why n={n} horizon={horizon} day={day} setDay={setDay} />
          </div>
        </section>
      )}
      {row && (
        <section className="section" aria-labelledby="perf-h">
          <div className="section-head"><h2 id="perf-h">{t("item.perf.title")}</h2><span className="chip evaluation">{t("chip.evaluation")}</span></div>
          <p>{t("item.perf.text", { best: pct(row.best_wape, 1), ref: pct(row.reference_wape, 1), cov: pct(row.coverage_80) })}</p>
        </section>
      )}
      <section className="section" aria-labelledby="odd-h">
        <div className="section-head"><h2 id="odd-h">{t("item.alerts.title")}</h2></div>
        {alerts.error && <ErrorBox problem={alerts.error} onRetry={alerts.reload} />}
        {alerts.data && (
          <>
            <p className="muted">{t("odd.note")}</p>
            {alerts.data.items.length === 0 ? <p>{t("item.alerts.none")}</p> : (
              <ul className="odd">
                {alerts.data.items.slice(0, 10).map((a) => (
                  <li key={a.date}>{t("next.odd.line", { item: a.item, date: dateLong(a.date), actual: num(a.actual), expected: num(a.expected), dir: a.direction === "higher" ? t("next.odd.above") : t("next.odd.below"), level: pct(alerts.data!.level), low: num(a.low), high: num(a.high) })}</li>
                ))}
              </ul>
            )}
          </>
        )}
        {!alerts.data && !alerts.error && <Loading text={t("next.odd.loading")} />}
      </section>
    </>
  );
}

function Why({ n, horizon, day, setDay }: { n: NextView; horizon: number; day: number; setDay: (d: number) => void }) {
  const { t } = useLang();
  const label = useMethodLabel();
  const r = n.reasons;
  const max = r ? Math.max(...r.items.slice(1).map((i) => Math.abs(i.units)), 1) : 1; // the typical-day base dwarfs the pushes, so it gets its own full bar
  const name = (reason: string, i: number) => (i === 0 ? t("reason.base") : t(`reason.${reason}`));
  return (
    <div>
      <h3>{t("next.why.title")}</h3>
      {!r ? (
        <p className="muted">{n.method_in_use === "learning model" ? "" : t("next.why.simple", { method: label(n.method_in_use) })}</p>
      ) : (
        <>
          <label className="field inline">
            <span>{t("next.why.for")}</span>
            <select value={day} onChange={(e) => setDay(Number(e.target.value))}>
              {Array.from({ length: horizon }, (_, i) => <option key={i} value={i}>{i === 0 ? t("next.why.tomorrow") : t("next.why.ahead", { n: i + 1 })}{n.dates[i] ? ` · ${dateShort(n.dates[i])}` : ""}</option>)}
            </select>
          </label>
          <p>{t("next.why.text", { date: dateLong(r.date), value: num(r.forecast) })}</p>
          <ul className="reasons">
            {r.items.map((it, i) => (
              <li key={it.reason} className={i === 0 ? "base" : it.units >= 0 ? "up" : "down"}>
                <span className="r-name">{name(it.reason, i)}</span>
                <span className="r-track" aria-hidden="true" dir="ltr"><span style={{ width: `${i === 0 ? 100 : (Math.abs(it.units) / max) * 100}%` }} /></span>
                <span className="r-val" dir="ltr">{i === 0 ? num(it.units) : `${it.units >= 0 ? "+" : "−"}${num(Math.abs(it.units))}`}</span>
              </li>
            ))}
          </ul>
          <p className="fine">{t("reason.note")}</p>
        </>
      )}
    </div>
  );
}
