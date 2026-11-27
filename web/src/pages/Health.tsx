import { useState } from "react";
import { api, IS_SNAPSHOT } from "../api/client";
import type { Challenger, Health as Result, HealthSignal, HealthStatus } from "../api/types";
import { ErrorBox, Loading } from "../components/States";
import { Link } from "react-router-dom";
import { useAsync, toProblem, type Problem } from "../hooks/useAsync";
import { useWidth } from "../hooks/useSize";
import { useLang } from "../i18n";
import { dateShort, num, pct } from "../lib/format";
import { useSession } from "../state/session";

const times = (x: number | null | undefined) => (x == null ? "–" : `×${num(x, 2)}`);

export function Status({ s }: { s: HealthStatus }) {
  const { t } = useLang();
  return <span className={`status ${s}`}>{t(`health.status.${s}`)}</span>;
}

/** The value of one signal as a person reads it, and its limits. */
function show(s: HealthSignal): { value: string; watch: string; action: string } {
  switch (s.key) {
    case "accuracy": case "vs_simple": return { value: times(s.value), watch: `> ${times(s.watch)}`, action: `> ${times(s.action)}` };
    case "bias": return { value: s.value == null ? "–" : `${s.value > 0 ? "+" : s.value < 0 ? "−" : ""}${pct(Math.abs(s.value), 1)}`, watch: `> ±${pct(s.watch)}`, action: `> ±${pct(s.action)}` };
    case "coverage": return { value: pct(s.value, 1), watch: `< ${pct(s.watch)}`, action: `< ${pct(s.action)}` };
    default: return { value: num(s.value, 2), watch: `> ${num(s.watch, 2)}`, action: "–" };
  }
}

function reason(s: HealthSignal, t: (k: string, p?: Record<string, string | number>) => string, r: Result): string {
  const base = { n: r.windows.n_recent };
  switch (s.key) {
    case "accuracy": return t("health.why.accuracy", { ...base, value: times(s.value), recent: pct(s.recent, 1), earlier: pct(s.earlier, 1) });
    case "vs_simple": return t("health.why.vs_simple", { value: times(s.value) });
    case "bias": return t(`health.why.bias.${(s.value ?? 0) > 0 ? "over" : "under"}`, { value: pct(Math.abs(s.value ?? 0), 1) });
    case "coverage": return t("health.why.coverage", { value: pct(s.value, 0) });
    default: return t("health.why.drift", { psi: num(s.value, 2) });
  }
}

export default function Health() {
  const { dataset, method } = useSession();
  const { t } = useLang();
  const res = useAsync((signal) => api.health(dataset!.id, method, signal), [dataset!.id, method]);
  const r = res.data;
  return (
    <>
      <header className="page-head">
        <h1>{t("health.title")}</h1>
        <p className="lede">{t("health.lede")}</p>
      </header>
      {res.error && <ErrorBox problem={res.error} onRetry={res.reload} />}
      {!r && !res.error && <Loading />}
      {r && <Body r={r} />}
    </>
  );
}

function Body({ r }: { r: Result }) {
  const { t, n } = useLang();
  const trouble = r.overall.signals.filter((s) => s.key !== "drift" && (s.status === "watch" || s.status === "action"));
  const drift = r.overall.signals.find((s) => s.key === "drift")!;
  return (
    <>
      <section className="section">
        <div className="section-head"><h2 id="health-now">{t("health.now")}</h2><span className="chip evaluation">{t("chip.evaluation")}</span></div>
        <p className="health-big"><Status s={r.overall.status} /></p>
        <p>{t(`health.status.${r.overall.status}.text`)}</p>
        <p className="muted">{t("health.asof", { date: dateShort(r.as_of), horizon: n("unit.day", r.horizon), count: r.windows.n_recent, from: r.windows.recent_from ? dateShort(r.windows.recent_from) : "–", to: r.windows.recent_to ? dateShort(r.windows.recent_to) : "–" })}</p>
        {(r.overall.status === "watch" || r.overall.status === "action") && <p><Link className="btn" to="/inventory">{t("health.review_orders")}</Link></p>}
        {trouble.length > 0 && <ul className="plain">{trouble.map((s) => <li key={s.key}><Status s={s.status} /> {reason(s, t, r)}</li>)}</ul>}
        <p className="fine">{t("health.counts", { healthy: r.counts.healthy, watch: r.counts.watch, action: r.counts.action, unknown: r.counts.unknown })}</p>
        {drift.status === "watch" && <p className="fine">{reason(drift, t, r)} {t("health.why.drift.note")}</p>}
      </section>



      <section className="section">
        <div className="section-head"><h2 id="health-time">{t("health.timeline")}</h2><span className="chip evaluation">{t("chip.evaluation")}</span></div>
        <p className="muted">{t("health.timeline.lede", { n: r.windows.n_recent })}</p>
        <Timeline r={r} />
      </section>

      <section className="section">
        <div className="section-head"><h2 id="health-items">{t("health.items")}</h2></div>
        <div className="table-wrap" tabIndex={0} role="region" aria-label={t("health.items")}>
          <table>
            <thead>
              <tr>
                <th scope="col">{t("score.items.item")}</th><th scope="col">{t("health.col.status")}</th><th scope="col" className="num">{t("health.sig.accuracy")}</th>
                <th scope="col" className="num">{t("health.sig.vs_simple")}</th><th scope="col" className="num">{t("health.sig.bias")}</th><th scope="col" className="num">{t("health.sig.coverage")}</th>
                <th scope="col" className="num">{t("health.col.demand")}</th>
              </tr>
            </thead>
            <tbody>
              {r.items.map((i) => {
                const g = (k: HealthSignal["key"]) => i.signals.find((s) => s.key === k);
                const cell = (k: HealthSignal["key"]) => { const s = g(k); return s ? show(s).value : "–"; };
                const level = i.drift.recent_mean != null && i.drift.earlier_mean ? i.drift.recent_mean / i.drift.earlier_mean - 1 : null;
                return (
                  <tr key={i.item}>
                    <th scope="row">{i.item}</th><td><Status s={i.status} /></td>
                    <td className="num">{cell("accuracy")}</td><td className="num">{cell("vs_simple")}</td><td className="num">{cell("bias")}</td><td className="num">{cell("coverage")}</td>
                    <td className="num">{level == null ? "–" : `${level > 0 ? "+" : level < 0 ? "−" : ""}${pct(Math.abs(level))}`}<small className="muted" style={{ display: "block" }}>PSI {num(i.drift.psi, 2)}</small></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p className="fine">{t("health.items.note")}</p>
      </section>

      <details className="more">
        <summary>{t("health.how")}</summary>
      <section className="section">
        <div className="section-head"><h2 id="health-sig">{t("health.signals")}</h2></div>
        <div className="table-wrap" tabIndex={0} role="region" aria-label={t("health.signals")}>
          <table>
            <thead><tr><th scope="col">{t("health.col.signal")}</th><th scope="col" className="num">{t("health.col.now")}</th><th scope="col">{t("health.col.watch")}</th><th scope="col">{t("health.col.action")}</th><th scope="col">{t("health.col.status")}</th></tr></thead>
            <tbody>
              {r.overall.signals.map((s) => {
                const v = show(s);
                return (
                  <tr key={s.key}>
                    <th scope="row">{t(`health.sig.${s.key}`)}<small className="muted" style={{ display: "block" }}>{t(`health.sig.${s.key}.desc`)}</small></th>
                    <td className="num">{v.value}</td><td>{v.watch}</td><td>{v.action}</td>
                    <td>{s.key === "drift" ? <span className="muted">{t(s.status === "watch" ? "health.shifted" : "health.stable")} · {t("health.info_only")}</span> : <Status s={s.status} />}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>
      <section className="section">
        <div className="section-head"><h2 id="health-rules">{t("health.rules")}</h2></div>
        <p className="muted">{t("health.rules.lede")}</p>
        <ul className="plain">{r.notes.map((c) => <li key={c} className="fine">{t(`health.note.${c}`)}</li>)}</ul>
      </section>
      </details>

      <details className="more">
        <summary>{t("health.advanced")}</summary>
        <Challenge method={r.method} />
      </details>


    </>
  );
}

function Timeline({ r }: { r: Result }) {
  const { t } = useLang();
  const [ref, width] = useWidth<HTMLDivElement>();
  const pts = r.timeline.filter((p) => p.rolling != null);
  if (pts.length < 2) return <p className="note-box">{t("health.timeline.none")}</p>;
  const H = 230, m = { l: 48, r: 14, t: 12, b: 28 };
  const max = Math.max(...pts.map((p) => Math.max(p.rolling ?? 0, p.rolling_reference ?? 0))) * 1.12 || 1;
  const x = (i: number) => m.l + (i / (pts.length - 1)) * (width - m.l - m.r);
  const y = (v: number) => H - m.b - (v / max) * (H - m.t - m.b);
  const line = (k: "rolling" | "rolling_reference") => pts.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p[k] ?? 0).toFixed(1)}`).join(" ");
  const last = pts[pts.length - 1];
  const ticks = [0, max / 2, max];
  return (
    <div className="panel">
      <ul className="legend" aria-label={t("replay.legend")}>
        <li><i className="sw line-solid" /> {t("health.legend.method")}</li>
        <li><i className="sw line-dash" /> {t("health.legend.simple")}</li>
      </ul>
      {/* measured inside the panel's padding, and allowed to shrink, so the chart never spills out of the box */}
      <div ref={ref} style={{ minWidth: 0, overflow: "hidden" }}>
      <svg width={width} height={H} role="img" aria-label={t("health.timeline.label", { method: r.method, last: pct(last.rolling, 1), simple: pct(last.rolling_reference, 1), from: dateShort(pts[0].known), to: dateShort(last.known) })}>
        {ticks.map((v) => <g key={v}><line x1={m.l} x2={width - m.r} y1={y(v)} y2={y(v)} stroke="var(--rule)" strokeWidth="1" /><text x={m.l - 6} y={y(v) + 4} textAnchor="end" fontSize="11" fill="var(--ink-2)">{pct(v)}</text></g>)}
        <path d={line("rolling_reference")} fill="none" stroke="var(--ink-2)" strokeWidth="2" strokeDasharray="6 4" />
        <path d={line("rolling")} fill="none" stroke="var(--pred)" strokeWidth="2.5" />
        <text x={m.l} y={H - 8} fontSize="11" fill="var(--ink-2)">{dateShort(pts[0].known)}</text>
        <text x={width - m.r} y={H - 8} fontSize="11" textAnchor="end" fill="var(--ink-2)">{dateShort(last.known)}</text>
      </svg>
      </div>
    </div>
  );
}

function Challenge({ method }: { method: string }) {
  const { dataset } = useSession();
  const { t } = useLang();
  const [state, setState] = useState<{ data: Challenger | null; error: Problem | null; loading: boolean }>({ data: null, error: null, loading: false });
  const run = () => {
    setState({ data: null, error: null, loading: true });
    api.challenger(dataset!.id, method).then((data) => setState({ data, error: null, loading: false }), (e) => setState({ data: null, error: toProblem(e), loading: false }));
  };
  const c = state.data;
  return (
    <section className="section">
      <div className="section-head"><h2 id="health-ch">{t("health.challenger")}</h2><span className="chip evaluation">{t("chip.evaluation")}</span></div>
      <p className="muted">{t("health.challenger.lede")}</p>
      <p><button className="btn" onClick={run} disabled={state.loading}>{IS_SNAPSHOT ? t("health.challenger.show") : t("health.challenger.run")}</button></p>
      {state.loading && <Loading />}
      {state.error && <ErrorBox problem={state.error} />}
      {c && (
        <>
          <div className="table-wrap" tabIndex={0} role="region" aria-label={t("health.challenger")}>
            <table>
              <thead><tr><th scope="col">{t("health.ch.who")}</th><th scope="col" className="num">{t("health.ch.wape")}</th><th scope="col" className="num">{t("health.sig.bias")}</th></tr></thead>
              <tbody>
                <tr><th scope="row">{t("health.ch.current")}</th><td className="num">{pct(c.current.wape, 2)}</td><td className="num">{pct(c.current.bias, 1)}</td></tr>
                <tr><th scope="row">{t("health.ch.challenger", { days: c.config.train_days })}</th><td className="num">{pct(c.challenger.wape, 2)}</td><td className="num">{pct(c.challenger.bias, 1)}</td></tr>
              </tbody>
            </table>
          </div>
          <p><strong>{t(`health.ch.${c.verdict}`, { gain: `${num(c.gain * 100, 2)}`, lo: num(c.gain_ci95[0] * 100, 2), hi: num(c.gain_ci95[1] * 100, 2), n: c.n_dates })}</strong></p>
          <p className="fine">{t("health.ch.range", { from: dateShort(c.from), to: dateShort(c.to), n: c.n_dates })}</p>
          <ul className="plain">{c.notes.map((k) => <li key={k} className="fine">{t(`health.note.${k}`)}</li>)}</ul>
        </>
      )}
    </section>
  );
}
