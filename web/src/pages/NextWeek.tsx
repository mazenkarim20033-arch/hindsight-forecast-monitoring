import { useMemo, useState } from "react";
import { api } from "../api/client";
import type { NextView } from "../api/types";
import { Pickers } from "../components/Pickers";
import { ErrorBox, Loading } from "../components/States";
import { Stage } from "../components/Stage";
import { useAsync } from "../hooks/useAsync";
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
  const [day, setDay] = useState(0);
  const next = useAsync((signal) => api.next(id, { item, method, level, day }, signal), [id, item, method, level, day]);
  const alerts = useAsync((signal) => api.alerts(id, { method }, signal), [id, method]);
  const n = next.data;
  const model = useMemo(() => (n ? liveModel(n) : null), [n]);
  if (!overview) return null;
  const horizon = overview.settings.horizon;
  return (
    <section className="page next">
      <header className="page-head">
        <h1>Next {horizon === 7 ? "week" : `${horizon} days`}</h1>
        <p className="lead small">The forecast from the last day in your file, with the range its track record supports. Look at the scorecard before relying on it.</p>
      </header>
      <Pickers overview={overview} />
      {next.error && <ErrorBox message={next.error} onRetry={next.reload} />}
      {!n && !next.error && <Loading text="Preparing the forecast" />}
      {n && model && (
        <>
          <div className="stage solo">
            <div className="stage-top">
              <div><span className="stage-kicker">Today is</span><strong className="stage-date">{dateLong(n.last_day)}</strong></div>
              <ul className="legend" aria-label="Chart key">
                <li><i className="sw actual" /> Real sales</li>
                <li><i className="sw fan" /> Forecast and its {pct(level)} range</li>
                <li><i className="sw curtain" /> Not yet known</li>
              </ul>
            </div>
            <Stage model={model} label={`Forecast for ${n.item}: the next ${horizon} days after ${n.last_day}, with a ${pct(level)} range.`} curtainText="Nobody knows yet" />
          </div>
          <div className="next-grid">
            <section className="card" aria-labelledby="days-h">
              <h2 id="days-h">Day by day</h2>
              <p className="muted">Expect about <strong>{num(n.total_next_7)}</strong> units over the next 7 days.{n.range_note ? ` ${n.range_note}` : ""}</p>
              <div className="scroll short" role="region" aria-label="Forecast for each day" tabIndex={0}>
                <table>
                  <thead><tr><th scope="col">Day</th><th scope="col">Best guess</th><th scope="col">{pct(level)} range</th></tr></thead>
                  <tbody>
                    {n.dates.map((d, i) => (
                      <tr key={d}>
                        <th scope="row">{dateLong(d)}</th>
                        <td className="num">{num(n.forecast[i])}</td>
                        <td className="num">{n.low[i] != null && n.high[i] != null ? `${num(n.low[i])} to ${num(n.high[i])}` : "n/a"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
            <Why n={n} horizon={horizon} day={day} setDay={setDay} />
          </div>
        </>
      )}
      <section className="card" aria-labelledby="odd-h">
        <h2 id="odd-h">Unusual days in the last year</h2>
        {alerts.error && <p className="muted">{alerts.error}</p>}
        {alerts.data && (
          <>
            <p className="muted">{alerts.data.note}</p>
            {alerts.data.items.length === 0 ? <p>No day fell outside its range.</p> : (
              <ul className="odd">
                {alerts.data.items.slice(0, 8).map((a) => (
                  <li key={`${a.item}${a.date}`}>
                    <strong>{a.item}</strong> on {dateLong(a.date)}: sold {num(a.actual)}, expected about {num(a.expected)} ({a.direction === "higher" ? "above" : "below"} the {pct(alerts.data!.level)} range of {num(a.low)} to {num(a.high)}).
                  </li>
                ))}
              </ul>
            )}
            {alerts.data.count > 8 && <p className="fine">{alerts.data.count - 8} more not shown.</p>}
          </>
        )}
        {!alerts.data && !alerts.error && <Loading text="Looking for unusual days" />}
      </section>
    </section>
  );
}

function Why({ n, horizon, day, setDay }: { n: NextView; horizon: number; day: number; setDay: (d: number) => void }) {
  const r = n.reasons;
  const max = r ? Math.max(...r.items.slice(1).map((i) => Math.abs(i.units)), 1) : 1; // the typical-day base is far larger than the pushes, so it gets its own full bar
  return (
    <section className="card" aria-labelledby="why-h">
      <h2 id="why-h">Why this forecast</h2>
      {!r ? (
        <p className="muted">{n.method_in_use === "learning model" ? "" : `This forecast comes from a simple rule (${n.method_in_use}), so there is nothing hidden to explain: it repeats a pattern from your recent weeks.`}</p>
      ) : (
        <>
          <label className="field inline">
            <span>Explain the forecast for</span>
            <select value={day} onChange={(e) => setDay(Number(e.target.value))}>
              {Array.from({ length: horizon }, (_, i) => <option key={i} value={i}>{i === 0 ? "tomorrow" : `${i + 1} days ahead`}{n.dates[i] ? ` · ${dateShort(n.dates[i])}` : ""}</option>)}
            </select>
          </label>
          <p>For {dateLong(r.date)} the model says <strong>{num(r.forecast)}</strong>. It starts from a typical day and adds or removes:</p>
          <ul className="reasons">
            {r.items.map((it, i) => (
              <li key={it.reason} className={i === 0 ? "base" : it.units >= 0 ? "up" : "down"}>
                <span className="r-name">{it.reason}</span>
                <span className="r-track" aria-hidden="true"><span style={{ width: `${i === 0 ? 100 : (Math.abs(it.units) / max) * 100}%` }} /></span>
                <span className="r-val">{i === 0 ? num(it.units) : `${it.units >= 0 ? "+" : "−"}${num(Math.abs(it.units))}`}</span>
              </li>
            ))}
          </ul>
          <p className="fine">{r.note}</p>
        </>
      )}
    </section>
  );
}
