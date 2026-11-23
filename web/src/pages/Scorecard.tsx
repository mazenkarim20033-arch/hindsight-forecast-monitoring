import { api } from "../api/client";
import type { MethodRow, Scorecard as ScorecardData } from "../api/types";
import { Check, Cross } from "../components/Mark";
import { useMethodLabel } from "../components/Pickers";
import { ErrorBox, Loading } from "../components/States";
import { useVerdictText } from "../components/verdict";
import { useAsync } from "../hooks/useAsync";
import { useLang } from "../i18n";
import { pct, signedPoints } from "../lib/format";
import { useSession } from "../state/session";
import { NoFile } from "./Replay";

export default function Scorecard() {
  const { dataset, overview } = useSession();
  if (!dataset || !overview) return <NoFile />;
  return <Inner id={dataset.id} />;
}

function Inner({ id }: { id: string }) {
  const { t } = useLang();
  const sc = useAsync((signal) => api.scorecard(id, signal), [id]);
  return (
    <section className="page scorecard">
      <header className="page-head">
        <h1>{t("score.title")}</h1>
        <p className="lead small">{t("score.lead")}</p>
      </header>
      {sc.error && <ErrorBox problem={sc.error} onRetry={sc.reload} />}
      {!sc.data && !sc.error && <Loading text={t("score.loading")} />}
      {sc.data && <Body sc={sc.data} />}
    </section>
  );
}

const LIMITS: Record<string, string> = {
  "Replay dates overlap, so the intervals shown are indicative.": "limit.overlap",
  "A good record on the past does not guarantee the future, especially after a change in the business.": "limit.future",
};

function Body({ sc }: { sc: ScorecardData }) {
  const { t } = useLang();
  const label = useMethodLabel();
  const verdictText = useVerdictText();
  const v = verdictText(sc.verdict);
  const rows = [...sc.methods].filter((r) => !r.is_auto).sort((a, b) => a.wape - b.wape);
  const auto = sc.methods.find((r) => r.is_auto);
  const max = Math.max(...sc.methods.map((r) => r.wape_ci95[1]), 0.001);
  return (
    <>
      <article className={`verdict ${sc.verdict.kind}`}>
        <div className="mark" aria-hidden="true">{sc.verdict.kind === "beats" ? <Check size={26} /> : sc.verdict.kind === "reference_best" ? <Cross size={22} /> : <span>≈</span>}</div>
        <div>
          <h2>{v.title}</h2>
          <p>{v.text}</p>
          {v.gain && <p className="fine">{v.gain}</p>}
        </div>
      </article>

      <section className="card" aria-labelledby="miss-h">
        <h2 id="miss-h">{t("score.miss.title")}</h2>
        <p className="muted">{t("score.miss.text")}</p>
        <ul className="bars">
          {rows.map((r) => (
            <li key={r.method} className={r.is_reference ? "ref" : r.method === sc.best_method ? "best" : ""}>
              <span className="bar-name">{label(r.method, r.is_reference, false)}</span>
              <span className="bar-track" aria-hidden="true" dir="ltr">
                <span className="bar-fill" style={{ width: `${(r.wape / max) * 100}%` }} />
                <span className="bar-ci" style={{ left: `${(r.wape_ci95[0] / max) * 100}%`, width: `${((r.wape_ci95[1] - r.wape_ci95[0]) / max) * 100}%` }} />
              </span>
              <span className="bar-val">{pct(r.wape, 1)}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="card table-card" aria-labelledby="det-h">
        <h2 id="det-h">{t("score.all.title")}</h2>
        <div className="scroll" role="region" aria-label={t("score.table.label")} tabIndex={0}>
          <table>
            <thead>
              <tr>
                <th scope="col">{t("score.col.method")}</th>
                <th scope="col">{t("score.col.miss")}</th>
                <th scope="col">{t("score.col.vs")}</th>
                <th scope="col">{t("score.col.ahead")}</th>
                <th scope="col">{t("score.col.split")}</th>
                <th scope="col">{t("score.col.range")}</th>
              </tr>
            </thead>
            <tbody>
              {[...rows, ...(auto ? [auto] : [])].map((r) => <Row key={r.method} r={r} />)}
            </tbody>
          </table>
        </div>
        <p className="fine">{t("score.ahead.note")}</p>
      </section>

      {sc.per_series.length > 1 && (
        <section className="card table-card" aria-labelledby="items-h">
          <h2 id="items-h">{t("score.items.title")}</h2>
          <div className="scroll" role="region" aria-label={t("score.items.label")} tabIndex={0}>
            <table>
              <thead><tr><th scope="col">{t("score.items.item")}</th><th scope="col">{t("score.items.ref")}</th><th scope="col">{label(sc.best_method, sc.best_method === sc.reference, false)}</th><th scope="col">{t("score.items.diff")}</th><th scope="col">{t("score.col.range")}</th></tr></thead>
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
        <h2 id="limits-h">{t("score.limits.title")}</h2>
        <ul className="plain">
          {sc.limits.map((l) => <li key={l}>{LIMITS[l] ? t(LIMITS[l]) : l}</li>)}
          <li>{t("score.limits.window", { n: sc.window.n_dates, h: sc.window.horizon })}</li>
        </ul>
      </section>
    </>
  );
}

function Row({ r }: { r: MethodRow }) {
  const { t } = useLang();
  const label = useMethodLabel();
  const gain = r.gain_vs_reference ?? 0;
  const ci = r.gain_ci95;
  const clear = ci && (ci[0] > 0 || ci[1] < 0);
  return (
    <tr className={r.is_reference ? "ref" : ""}>
      <th scope="row">{label(r.method, r.is_reference, r.is_auto)}</th>
      <td className="num">{pct(r.wape, 1)}</td>
      <td className="num">{r.is_reference ? t("score.yardstick") : (
        <span className={clear ? (gain > 0 ? "good" : "bad") : ""}>{signedPoints(gain)}{ci ? <span className="ci"> ({t("score.to", { a: signedPoints(ci[0]), b: signedPoints(ci[1]) })})</span> : null}{clear ? "" : ` · ${t("score.unclear")}`}</span>
      )}</td>
      <td className="num">{r.is_reference ? "–" : pct(r.win_rate_vs_reference)}</td>
      <td className="num">{pct(r.wape_days_1_7, 1)} · {r.wape_days_8_28 == null ? "–" : pct(r.wape_days_8_28, 1)}</td>
      <td className="num">{pct(r.coverage_80)}</td>
    </tr>
  );
}
