import { useState } from "react";
import { api, IS_SNAPSHOT } from "../api/client";
import type { AuditDecision, AuditReviewRow, OutcomeEvaluation, StrategyKey } from "../api/types";
import { Status } from "./Health";
import { ErrorBox, Loading } from "../components/States";
import { useAsync, toProblem } from "../hooks/useAsync";
import { useLang, useServerText } from "../i18n";
import { dateShort, num, pct } from "../lib/format";
import { useSession } from "../state/session";

const money = (x: number | null | undefined) => (x == null ? "–" : num(x, 0));

export default function Audit() {
  const { dataset } = useSession();
  const { t } = useLang();
  const say = useServerText();
  const res = useAsync((signal) => (IS_SNAPSHOT ? Promise.resolve(null) : api.auditEvents(signal)), [dataset?.id]);
  const [review, setReview] = useState<Record<number, AuditReviewRow>>({});
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const list = res.data;

  const check = async () => {
    setBusy(true); setMsg(null);
    try { setReview(Object.fromEntries((await api.auditReview(dataset!.id)).decisions.map((r) => [r.decision_id, r]))); } catch (e) { setMsg(say(toProblem(e), "problem")); } finally { setBusy(false); }
  };
  const saveOutcome = async (id: number) => {
    setMsg(null);
    try { await api.auditOutcome(dataset!.id, id); await check(); res.reload(); } catch (e) { setMsg(say(toProblem(e), "problem")); }
  };
  const exportLog = async () => {
    try {
      const url = URL.createObjectURL(new Blob([JSON.stringify(await api.auditExport(), null, 2)], { type: "application/json" }));
      const a = document.createElement("a");
      a.href = url; a.download = "hindsight-audit-log.json"; a.click();
      URL.revokeObjectURL(url);
    } catch (e) { setMsg(say(toProblem(e), "problem")); }
  };

  return (
    <>
      <header className="page-head">
        <h1>{t("audit.title")}</h1>
        <p className="lede">{t("audit.lede")}</p>
      </header>
      {IS_SNAPSHOT && <p className="note-box">{t("audit.snapshot")}</p>}
      {res.error && <ErrorBox problem={res.error} onRetry={res.reload} />}
      {!list && !res.error && !IS_SNAPSHOT && <Loading />}
      {list && (
        <>
          <section className="section">
            <div className="section-head"><h2>{t("audit.integrity")}</h2></div>
            <p className="verify">{list.verify.ok ? <span className="status healthy">{t("audit.intact", { n: list.verify.n })}</span> : <span className="status action">{t("audit.altered", { id: list.verify.bad_id ?? 0 })}</span>}</p>
            <p className="fine">{t("audit.integrity.note")}</p>
            <p className="toolbar">
              <button className="btn" onClick={check} disabled={busy || list.decisions.length === 0}>{t("audit.check")}</button>
              <button className="btn" onClick={exportLog} disabled={list.verify.n === 0}>{t("audit.export")}</button>
            </p>
            <p className="fine">{t("audit.check.lede")}</p>
            {msg && <p role="alert" className="alert-box">{msg}</p>}
          </section>

          <section className="section">
            <div className="section-head"><h2>{t("audit.decisions")}</h2></div>
            {list.decisions.length === 0 && <p className="note-box">{t("audit.empty")}</p>}
            {list.decisions.map((d) => <Decision key={d.id} d={d} row={review[d.id]} onSave={() => saveOutcome(d.id)} />)}
          </section>
        </>
      )}
    </>
  );
}

function Decision({ d, row, onSave }: { d: AuditDecision; row?: AuditReviewRow; onSave: () => void }) {
  const { t, n } = useLang();
  const p = d.payload;
  const when = d.ts.replace("T", " ").replace(/\+00:00$/, " UTC");
  const changed = p.items.filter((i) => i.overridden).length;
  const ev: OutcomeEvaluation | undefined = d.outcome?.payload ?? row?.preview;
  return (
    <article className="card" style={{ marginBottom: "1rem" }}>
      <h3>{t("audit.decision", { id: d.id })} <small className="muted">{when}</small></h3>
      <p>
        {t("audit.summary", { file: p.dataset.filename, asof: dateShort(p.dataset.as_of), days: n("unit.day", p.window_days), option: t(`inv.strategy.${p.strategy}`), total: num(p.total_ordered) })}
        {changed > 0 && <> {t("audit.changed", { n: changed })}</>}
      </p>
      <p className="fine">
        {p.health && <>{t("audit.health")}: <Status s={p.health} />. </>}
        {p.scenario && <span className="chip dataset">{t("chip.hypothetical")}: {p.scenario.name}</span>}
      </p>
      {p.note && <blockquote className="quote" dir="auto">{p.note}</blockquote>}
      <details>
        <summary>{t("audit.items")}</summary>
        <div className="table-wrap" tabIndex={0} role="region" aria-label={`${t("audit.items")} #${d.id}`}>
          <table>
            <thead><tr><th scope="col">{t("score.items.item")}</th><th scope="col" className="num">{t("inv.c.forecast")}</th><th scope="col" className="num">{t("inv.c.position")}</th><th scope="col" className="num">{t("rec.recommended")}</th><th scope="col" className="num">{t("rec.ordered")}</th></tr></thead>
            <tbody>
              {p.items.map((i) => (
                <tr key={i.item}>
                  <th scope="row">{i.item}</th><td className="num">{num(i.forecast_demand)}</td><td className="num">{num(i.position)}</td>
                  <td className="num">{num(i.by_strategy[p.strategy]?.order)}</td><td className="num"><strong>{num(i.chosen_order)}</strong>{i.overridden && <small className="muted" style={{ display: "block" }}>{t("audit.overridden")}</small>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>

      <h4>{t("audit.outcome")}</h4>
      {d.outcome ? <p className="fine">{t("audit.outcome.saved", { id: d.outcome.id, file: d.outcome.payload.dataset.filename })}</p> : row ? (
        <p className="fine">
          {t(`audit.status.${row.status}`, Object.fromEntries(Object.entries(row.params).map(([k, v]) => [k, String(v)])))}
          {row.status === "ready" && <> <button className="btn" onClick={onSave}>{t("audit.outcome.save")}</button></>}
        </p>
      ) : <p className="fine">{t("audit.outcome.pending")}</p>}
      {ev && <Outcome ev={ev} strategy={p.strategy} saved={!!d.outcome} />}
    </article>
  );
}

function Outcome({ ev, strategy, saved }: { ev: OutcomeEvaluation; strategy: StrategyKey; saved: boolean }) {
  const { t } = useLang();
  return (
    <>
      {!saved && <p className="note-box">{t("audit.preview")}</p>}
      <p className="muted">{t("audit.window", { from: dateShort(ev.window.from), to: dateShort(ev.window.to) })} {t("audit.totals", { actual: num(ev.totals.actual), forecast: num(ev.totals.forecast), error: ev.forecast_error == null ? "–" : pct(Math.abs(ev.forecast_error), 1), dir: t(`audit.dir.${(ev.forecast_error ?? 0) > 0 ? "over" : "under"}`) })}</p>
      <div className="table-wrap" tabIndex={0} role="region" aria-label={t("audit.outcome")}>
        <table>
          <thead><tr><th scope="col">{t("score.items.item")}</th><th scope="col" className="num">{t("audit.actual")}</th><th scope="col" className="num">{t("audit.available")}</th><th scope="col" className="num">{t("audit.left")}</th><th scope="col" className="num">{t("audit.short")}</th><th scope="col" className="num">{t("audit.cost")}</th></tr></thead>
          <tbody>
            {ev.items.map((i) => (
              <tr key={i.item}><th scope="row">{i.item}</th><td className="num">{num(i.actual)}</td><td className="num">{num(i.chosen.level)}</td><td className="num">{num(i.chosen.leftover)}</td><td className="num">{num(i.chosen.shortage)}</td><td className="num">{money(i.chosen.cost)}</td></tr>
            ))}
            <tr><th scope="row">{t("audit.total")}</th><td className="num">{num(ev.totals.actual)}</td><td className="num">–</td><td className="num">{num(ev.totals.leftover)}</td><td className="num">{num(ev.totals.shortage)}</td><td className="num">{money(ev.totals.cost)}</td></tr>
          </tbody>
        </table>
      </div>
      {Object.keys(ev.by_strategy).length > 0 && (
        <>
          <p className="muted">{t("audit.alt")}</p>
          <ul className="plain">
            {(Object.entries(ev.by_strategy) as [StrategyKey, { leftover: number; shortage: number; cost: number | null }][]).map(([k, v]) => (
              <li key={k}>{k === strategy ? <strong>{t(`inv.strategy.${k}`)}</strong> : t(`inv.strategy.${k}`)}: {t("audit.alt.row", { left: num(v.leftover), short: num(v.shortage), cost: money(v.cost) })}{ev.best_in_hindsight === k && <> ({t("audit.best")})</>}</li>
            ))}
          </ul>
        </>
      )}
      <p className="fine">{t("audit.fine")}</p>
    </>
  );
}
