import { useMemo, useState } from "react";
import { api } from "../api/client";
import type { NextView } from "../api/types";
import { Pickers, useMethodLabel } from "../components/Pickers";
import { ErrorBox, Loading } from "../components/States";
import { Stage } from "../components/Stage";
import { useAsync } from "../hooks/useAsync";
import { useLang } from "../i18n";
import { dateLong, dateShort, num, pct } from "../lib/format";
import { liveModel } from "../lib/models";
import { useSession } from "../state/session";
import { NoFile } from "./Replay";

export default function NextWeek() {
  const { dataset, overview } = useSession();
  if (!dataset || !overview) return <NoFile />;
  return <Inner id={dataset.id} />;
}

function Inner({ id }: { id: string }) {
  const { overview, item, method, level } = useSession();
  const { t } = useLang();
  const [day, setDay] = useState(0);
  const next = useAsync((signal) => api.next(id, { item, method, level, day }, signal), [id, item, method, level, day]);
  const alerts = useAsync((signal) => api.alerts(id, { method }, signal), [id, method]);
  const nx = next.data;
  const model = useMemo(() => (nx ? liveModel(nx) : null), [nx]);
  if (!overview) return null;
  const horizon = overview.settings.horizon;
  return (
    <section className="page next">
      <header className="page-head">
        <h1>{horizon === 7 ? t("next.title.week") : t("next.title.days", { n: horizon })}</h1>
        <p className="lead small">{t("next.lead")}</p>
      </header>
      <Pickers overview={overview} />
      {next.error && <ErrorBox problem={next.error} onRetry={next.reload} />}
      {!nx && !next.error && <Loading text={t("next.loading")} />}
      {nx && model && (
        <>
          <div className="stage solo">
            <div className="stage-top">
              <div><span className="stage-kicker">{t("next.today")}</span><strong className="stage-date">{dateLong(nx.last_day)}</strong></div>
              <ul className="legend" aria-label={t("replay.legend")}>
                <li><i className="sw actual" /> {t("replay.legend.actual")}</li>
                <li><i className="sw fan" /> {t("replay.legend.fan.level", { level: pct(level) })}</li>
                <li><i className="sw curtain" /> {t("replay.legend.curtain")}</li>
              </ul>
            </div>
            <Stage model={model} label={t("next.stage.label", { item: nx.item, n: horizon, date: nx.last_day, level: pct(level) })} curtainText={t("stage.unknown")} />
          </div>
          <div className="next-grid">
            <section className="card" aria-labelledby="days-h">
              <h2 id="days-h">{t("next.days.title")}</h2>
              <p className="muted">{t("next.expect", { total: num(nx.total_next_7) })}{nx.range_note ? ` ${t("next.range.none")}` : ""}</p>
              <div className="scroll short" role="region" aria-label={t("next.days.label")} tabIndex={0}>
                <table>
                  <thead><tr><th scope="col">{t("next.col.day")}</th><th scope="col">{t("next.col.guess")}</th><th scope="col">{t("next.col.range", { level: pct(level) })}</th></tr></thead>
                  <tbody>
                    {nx.dates.map((d, i) => (
                      <tr key={d}>
                        <th scope="row">{dateLong(d)}</th>
                        <td className="num">{num(nx.forecast[i])}</td>
                        <td className="num">{nx.low[i] != null && nx.high[i] != null ? t("score.to", { a: num(nx.low[i]), b: num(nx.high[i]) }) : "–"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
            <Why n={nx} horizon={horizon} day={day} setDay={setDay} />
          </div>
        </>
      )}
      <section className="card" aria-labelledby="odd-h">
        <h2 id="odd-h">{t("next.odd.title")}</h2>
        {alerts.error && <ErrorBox problem={alerts.error} onRetry={alerts.reload} />}
        {alerts.data && (
          <>
            <p className="muted">{t("odd.note")}</p>
            {alerts.data.items.length === 0 ? <p>{t("next.odd.none")}</p> : (
              <ul className="odd">
                {alerts.data.items.slice(0, 8).map((a) => (
                  <li key={`${a.item}${a.date}`}>
                    {t("next.odd.line", { item: a.item, date: dateLong(a.date), actual: num(a.actual), expected: num(a.expected), dir: a.direction === "higher" ? t("next.odd.above") : t("next.odd.below"), level: pct(alerts.data!.level), low: num(a.low), high: num(a.high) })}
                  </li>
                ))}
              </ul>
            )}
            {alerts.data.count > 8 && <p className="fine">{t("next.odd.more", { n: alerts.data.count - 8 })}</p>}
          </>
        )}
        {!alerts.data && !alerts.error && <Loading text={t("next.odd.loading")} />}
      </section>
    </section>
  );
}

function Why({ n, horizon, day, setDay }: { n: NextView; horizon: number; day: number; setDay: (d: number) => void }) {
  const { t } = useLang();
  const label = useMethodLabel();
  const r = n.reasons;
  const max = r ? Math.max(...r.items.slice(1).map((i) => Math.abs(i.units)), 1) : 1; // the typical-day base is far larger than the pushes, so it gets its own full bar
  const reasonName = (name: string, i: number) => (i === 0 ? t("reason.base") : t(`reason.${name}`));
  return (
    <section className="card" aria-labelledby="why-h">
      <h2 id="why-h">{t("next.why.title")}</h2>
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
                <span className="r-name">{reasonName(it.reason, i)}</span>
                <span className="r-track" aria-hidden="true" dir="ltr"><span style={{ width: `${i === 0 ? 100 : (Math.abs(it.units) / max) * 100}%` }} /></span>
                <span className="r-val" dir="ltr">{i === 0 ? num(it.units) : `${it.units >= 0 ? "+" : "−"}${num(Math.abs(it.units))}`}</span>
              </li>
            ))}
          </ul>
          <p className="fine">{t("reason.note")}</p>
        </>
      )}
    </section>
  );
}
