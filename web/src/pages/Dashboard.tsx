import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { DashItem } from "../api/types";
import { ForecastChart } from "../components/ForecastChart";
import { HealthSection } from "../components/HealthNote";
import { Pickers, useMethodLabel } from "../components/Pickers";
import { ErrorBox, Loading } from "../components/States";
import { useVerdictText } from "../components/verdict";
import { useAsync } from "../hooks/useAsync";
import { useLang } from "../i18n";
import { dateLong, num, pct } from "../lib/format";
import { useSession } from "../state/session";

export function changeLabel(c: number | null): string {
  return c == null ? "–" : `${c > 0 ? "+" : c < 0 ? "−" : ""}${pct(Math.abs(c), 1)}`;
}

export function ChangeCell({ c }: { c: number | null }) {
  return <span className={c == null ? "" : c > 0.02 ? "good" : c < -0.02 ? "bad" : ""}>{changeLabel(c)}</span>;
}

export function ItemStatus({ n }: { n: number }) {
  const { t } = useLang();
  return n === 0 ? <span className="status normal">{t("items.status.normal")}</span> : <span className="status warning">{t("items.status.unusual", { n })}</span>;
}

export default function Dashboard() {
  const { dataset, overview, method, level } = useSession();
  const { t, n } = useLang();
  const label = useMethodLabel();
  const verdictText = useVerdictText();
  const id = dataset!.id;
  const dash = useAsync((signal) => api.dashboard(id, { method }, signal), [id, method]);
  const total = useAsync((signal) => api.total(id, { method, level }, signal), [id, method, level]);
  const d = dash.data;
  const change = d && d.totals.last_7 > 0 ? d.totals.next_7 / d.totals.last_7 - 1 : null;
  const kind = change == null || Math.abs(change) < 0.02 ? "flat" : change > 0 ? "up" : "down";
  const movers: DashItem[] = d ? [...d.items].sort((a, b) => Math.abs(b.change ?? 0) - Math.abs(a.change ?? 0)).slice(0, 5) : [];
  return (
    <>
      <header className="page-head">
        <h1>{t("dash.title")}</h1>
        {d && overview && <p className="lede">{t("dash.lede", { items: n("unit.item", overview.series.length), days: n("unit.day", overview.dates.n_days), last: dateLong(d.last_day), method: label(d.method_in_use) })}</p>}
      </header>
      {overview && <Pickers overview={overview} />}
      {dash.error && <ErrorBox problem={dash.error} onRetry={dash.reload} />}
      {!d && !dash.error && <Loading text={t("state.loading")} />}
      {d && overview && (
        <div className="with-margin">
          <div>
            <p className="headline">
              {t(`dash.headline.${kind}`, { pct: pct(Math.abs(change ?? 0), 1), next: num(d.totals.next_7), last: num(d.totals.last_7) })}
            </p>
            <div className="kpis" role="list">
              <div className="kpi" role="listitem"><span className="label">{t("dash.kpi.next")}</span><span className="value">{num(d.totals.next_7)}</span><span className="sub">{changeLabel(change)}</span></div>
              <div className="kpi" role="listitem"><span className="label">{t("dash.kpi.last")}</span><span className="value">{num(d.totals.last_7)}</span><span className="sub">{t("replay.legend.actual")}</span></div>
              <div className="kpi" role="listitem"><span className="label">{t("dash.kpi.range")}</span><span className="value">{pct(d.trust.coverage_80)}</span><span className="sub">{t("dash.kpi.range.sub")}</span></div>
              <div className="kpi" role="listitem"><span className="label">{t("dash.kpi.unusual")}</span><span className="value">{num(d.unusual_30d)}</span><span className="sub">{t("dash.kpi.unusual.sub")}</span></div>
            </div>

            <section className="section" aria-labelledby="chart-h">
              <div className="section-head"><h2 id="chart-h">{t("dash.chart.title")}</h2><span className="chip prediction">{t("chip.forecast")}</span></div>
              {total.error && <ErrorBox problem={total.error} onRetry={total.reload} />}
              {total.data ? <ForecastChart next={total.data} level={level} horizon={d.horizon} /> : !total.error && <Loading />}
            </section>

            <section className="section" aria-labelledby="items-h">
              <div className="section-head"><h2 id="items-h">{t("dash.items.title")}</h2><Link to="/items">{t("dash.items.all")}</Link></div>
              <div className="table-wrap">
                <table>
                  <thead><tr><th scope="col">{t("items.col.item")}</th><th scope="col" className="num">{t("items.col.last")}</th><th scope="col" className="num">{t("items.col.next")}</th><th scope="col" className="num">{t("items.col.change")}</th><th scope="col">{t("items.col.status")}</th></tr></thead>
                  <tbody>
                    {movers.map((it) => (
                      <tr key={it.id}>
                        <th scope="row"><Link className="tbl-link" to={`/items/${encodeURIComponent(it.id)}`}>{it.id}</Link></th>
                        <td className="num">{num(it.last_7)}</td><td className="num">{num(it.next_7)}</td>
                        <td className="num"><ChangeCell c={it.change} /></td>
                        <td><ItemStatus n={it.unusual_30d} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            <section className="section" aria-labelledby="odd-h">
              <div className="section-head"><h2 id="odd-h">{t("dash.unusual.title")}</h2></div>
              {d.recent_unusual.length === 0 ? <p>{t("dash.unusual.none")}</p> : (
                <ul className="odd">
                  {d.recent_unusual.map((u) => (
                    <li key={u.item + u.date}>{t("dash.unusual.line", { item: u.item, date: dateLong(u.date), actual: num(u.actual), expected: num(u.expected), dir: t(`dash.unusual.${u.direction}`) })}</li>
                  ))}
                </ul>
              )}
            </section>

            <HealthSection />

            <section className="section" aria-labelledby="trust-h">
              <div className="section-head"><h2 id="trust-h">{t("dash.trust.title")}</h2><span className="chip evaluation">{t("chip.evaluation")}</span></div>
              <p>{verdictText(d.verdict).text}</p>
              <Link className="btn" to="/scorecard">{t("dash.trust.open")}</Link>
            </section>
          </div>
          <aside className="margin-notes" aria-label="Notes">
            <p><span className="chip prediction">{t("chip.forecast")}</span><br />{t("dash.note.1", { chip: "" }).trim()}</p>
            <p><span className="chip actual">{t("chip.actual")}</span><br />{t("dash.note.2", { chip: "" }).trim()}</p>
            <p><span className="chip evaluation">{t("chip.evaluation")}</span><br />{t("dash.note.3", { chip: "" }).trim()}</p>
          </aside>
        </div>
      )}
    </>
  );
}
