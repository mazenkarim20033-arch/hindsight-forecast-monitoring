import { api } from "../api/client";
import type { MethodRow, Scorecard as ScorecardData } from "../api/types";
import { Check, Cross } from "../components/Mark";
import { methodLabel } from "../components/Pickers";
import { ErrorBox, Loading } from "../components/States";
import { useAsync } from "../hooks/useAsync";
import { pct, signedPoints } from "../lib/format";
import { useSession } from "../state/session";
import { NoFile } from "./Replay";

export default function Scorecard() {
  const { dataset, overview } = useSession();
  if (!dataset || !overview) return <NoFile />;
  return <Inner id={dataset.id} />;
}

function Inner({ id }: { id: string }) {
  const sc = useAsync((signal) => api.scorecard(id, signal), [id]);
  return (
    <section className="page scorecard">
      <header className="page-head">
        <h1>Scorecard</h1>
        <p className="lead small">Did the cleverer methods earn their place? Every number below comes from the replay: forecasts made with only the past, judged on what happened.</p>
      </header>
      {sc.error && <ErrorBox message={sc.error} onRetry={sc.reload} />}
      {!sc.data && !sc.error && <Loading text="Scoring the replay" />}
      {sc.data && <Body sc={sc.data} />}
    </section>
  );
}

const KIND_TITLE: Record<string, string> = {
  beats: "A cleverer method is worth using",
  tie: "Too close to call",
  worse: "The simple rule is as good",
  reference_best: "The simple rule wins",
};

function Body({ sc }: { sc: ScorecardData }) {
  const v = sc.verdict;
  const rows = [...sc.methods].filter((r) => !r.is_auto).sort((a, b) => a.wape - b.wape);
  const auto = sc.methods.find((r) => r.is_auto);
  const max = Math.max(...sc.methods.map((r) => r.wape_ci95[1]), 0.001);
  return (
    <>
      <article className={`verdict ${v.kind}`}>
        <div className="mark" aria-hidden="true">{v.kind === "beats" ? <Check size={26} /> : v.kind === "reference_best" ? <Cross size={22} /> : <span>≈</span>}</div>
        <div>
          <h2>{KIND_TITLE[v.kind]}</h2>
          <p>{v.text}</p>
          {v.kind === "beats" && v.gain_ci95 && (
            <p className="fine">Average gain over the simple rule: {signedPoints(v.gain)} of sales (the plausible range is {signedPoints(v.gain_ci95[0])} to {signedPoints(v.gain_ci95[1])}).</p>
          )}
        </div>
      </article>

      <section className="card" aria-labelledby="miss-h">
        <h2 id="miss-h">Average miss by method</h2>
        <p className="muted">How far off the daily forecast was, as a share of total sales. Lower is better. The thin line is a 95% interval; where intervals overlap the methods are hard to separate.</p>
        <ul className="bars">
          {rows.map((r) => (
            <li key={r.method} className={r.is_reference ? "ref" : r.method === sc.best_method ? "best" : ""}>
              <span className="bar-name">{methodLabel(r.method, r.is_reference, false)}</span>
              <span className="bar-track" aria-hidden="true">
                <span className="bar-fill" style={{ width: `${(r.wape / max) * 100}%` }} />
                <span className="bar-ci" style={{ left: `${(r.wape_ci95[0] / max) * 100}%`, width: `${((r.wape_ci95[1] - r.wape_ci95[0]) / max) * 100}%` }} />
              </span>
              <span className="bar-val">{pct(r.wape, 1)}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="card table-card" aria-labelledby="det-h">
        <h2 id="det-h">All the numbers</h2>
        <div className="scroll" role="region" aria-label="Scorecard table" tabIndex={0}>
          <table>
            <thead>
              <tr>
                <th scope="col">Method</th>
                <th scope="col">Average miss</th>
                <th scope="col">Compared with the simple rule</th>
                <th scope="col">Ahead on</th>
                <th scope="col">First week vs weeks 2 to 4</th>
                <th scope="col">80% range held</th>
              </tr>
            </thead>
            <tbody>
              {[...rows, ...(auto ? [auto] : [])].map((r) => <Row key={r.method} r={r} />)}
            </tbody>
          </table>
        </div>
        <p className="fine">“Ahead on” is the share of replay dates where the method’s total error was smaller than the simple rule’s. A good 80% range holds on about 80% of days.</p>
      </section>

      {sc.per_series.length > 1 && (
        <section className="card table-card" aria-labelledby="items-h">
          <h2 id="items-h">By item</h2>
          <div className="scroll" role="region" aria-label="Scores by item" tabIndex={0}>
            <table>
              <thead><tr><th scope="col">Item</th><th scope="col">Simple rule miss</th><th scope="col">{methodLabel(sc.best_method, sc.best_method === sc.reference, false)}</th><th scope="col">Difference</th><th scope="col">80% range held</th></tr></thead>
              <tbody>
                {sc.per_series.map((s) => (
                  <tr key={s.series}>
                    <th scope="row">{s.series}</th>
                    <td className="num">{pct(s.reference_wape, 1)}</td>
                    <td className="num">{pct(s.best_wape, 1)}</td>
                    <td className={`num ${s.gain > 0.0005 ? "good" : s.gain < -0.0005 ? "bad" : ""}`}>{signedPoints(s.gain)}</td>
                    <td className="num">{pct(s.coverage_80)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <section className="card" aria-labelledby="limits-h">
        <h2 id="limits-h">What this does not tell you</h2>
        <ul className="plain">
          {sc.limits.map((l) => <li key={l}>{l}</li>)}
          <li>Scored on {sc.window.n_dates} replay dates, each forecasting {sc.window.horizon} days ahead.</li>
        </ul>
      </section>
    </>
  );
}

function Row({ r }: { r: MethodRow }) {
  const gain = r.gain_vs_reference ?? 0;
  const ci = r.gain_ci95;
  const clear = ci && (ci[0] > 0 || ci[1] < 0);
  return (
    <tr className={r.is_reference ? "ref" : ""}>
      <th scope="row">{methodLabel(r.method, r.is_reference, r.is_auto)}</th>
      <td className="num">{pct(r.wape, 1)}</td>
      <td className="num">{r.is_reference ? "the yardstick" : (
        <span className={clear ? (gain > 0 ? "good" : "bad") : ""}>{signedPoints(gain)}{ci ? <span className="ci"> ({signedPoints(ci[0])} to {signedPoints(ci[1])})</span> : null}{clear ? "" : " · unclear"}</span>
      )}</td>
      <td className="num">{r.is_reference ? "n/a" : pct(r.win_rate_vs_reference)}</td>
      <td className="num">{pct(r.wape_days_1_7, 1)} · {r.wape_days_8_28 == null ? "n/a" : pct(r.wape_days_8_28, 1)}</td>
      <td className="num">{pct(r.coverage_80)}</td>
    </tr>
  );
}
