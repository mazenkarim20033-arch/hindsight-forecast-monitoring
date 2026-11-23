import { useEffect, useRef, useState, type DragEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { AnalysisSettings, DatasetSummary, Job } from "../api/types";
import { HeroStage, Mark } from "../components/Mark";
import { useMethodLabel } from "../components/Pickers";
import { toProblem, type Problem } from "../hooks/useAsync";
import { useLang, useServerText } from "../i18n";
import { pct } from "../lib/format";
import { useSession } from "../state/session";

type Phase = "choose" | "check" | "running";

export default function Start() {
  const { dataset, setDataset, setOverview, restoring } = useSession();
  const { t } = useLang();
  const say = useServerText();
  const [phase, setPhase] = useState<Phase>("choose");
  const [error, setError] = useState<Problem | null>(null);
  const [busy, setBusy] = useState(false);
  const [job, setJob] = useState<Job | null>(null);
  const [horizon, setHorizon] = useState<AnalysisSettings["horizon"]>(28);
  const [calendar, setCalendar] = useState<AnalysisSettings["calendar"]>("none");
  const navigate = useNavigate();
  const timer = useRef<number | undefined>();

  useEffect(() => () => window.clearTimeout(timer.current), []);
  useEffect(() => {
    if (dataset && phase === "choose" && !job) setPhase("check");
  }, [dataset, phase, job]);

  async function receive(make: () => Promise<DatasetSummary>) {
    setBusy(true);
    setError(null);
    try {
      const d = await make();
      setDataset(d);
      setCalendar(d.has_events ? "events" : "none");
      setPhase("check");
    } catch (e) {
      setError(toProblem(e));
    } finally {
      setBusy(false);
    }
  }

  async function start() {
    if (!dataset) return;
    setError(null);
    try {
      const j = await api.analyze(dataset.id, { horizon, calendar });
      setJob(j);
      setPhase("running");
      poll(j.id);
    } catch (e) {
      setError(toProblem(e));
    }
  }

  function poll(id: string) {
    timer.current = window.setTimeout(async () => {
      try {
        const j = await api.job(id);
        setJob(j);
        if (j.state === "running") return poll(id);
        if (j.state === "failed") { setError({ message: j.error ?? "The replay stopped unexpectedly." }); setPhase("check"); return; }
        if (dataset) {
          setOverview(await api.overview(dataset.id));
          setDataset({ ...dataset, analyzed: true });
          navigate("/replay");
        }
      } catch (e) {
        setError(toProblem(e));
        setPhase("check");
      }
    }, 500);
  }

  if (restoring) return <section className="page narrow"><p className="muted" role="status">{t("state.restoring")}</p></section>;

  return (
    <section className="page start">
      {phase === "choose" && <Choose busy={busy} error={error ? say(error, "problem") : null} onFile={(f) => receive(() => api.upload(f))} onSample={() => receive(() => api.sample())} />}
      {phase === "check" && dataset && (
        <Check
          dataset={dataset} error={error ? say(error, "problem") : null} horizon={horizon} calendar={calendar}
          setHorizon={setHorizon} setCalendar={setCalendar}
          onChange={setDataset} onStart={start}
          onOther={() => { setDataset(null); setPhase("choose"); setError(null); }}
        />
      )}
      {phase === "running" && <Running job={job} sample={dataset?.is_sample ?? false} full={dataset?.plan.tier === "full"} />}
    </section>
  );
}

function Choose({ busy, error, onFile, onSample }: { busy: boolean; error: string | null; onFile: (f: File) => void; onSample: () => void }) {
  const { t } = useLang();
  const [over, setOver] = useState(false);
  const drop = (e: DragEvent) => {
    e.preventDefault();
    setOver(false);
    const f = e.dataTransfer.files?.[0];
    if (f) onFile(f);
  };
  return (
    <>
      <div className="hero">
        <div className="hero-text">
          <Mark size={44} />
          <h1>{t("start.title")}</h1>
          <p className="lead">{t("start.lead")}</p>
        </div>
        <HeroStage />
      </div>
      <div className="start-grid">
        <label className={`drop${over ? " over" : ""}${busy ? " busy" : ""}`} onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)} onDrop={drop}>
          <input type="file" accept=".csv,.xlsx,.xls,.txt,.tsv" disabled={busy} onChange={(e) => { const f = e.target.files?.[0]; if (f) onFile(f); e.target.value = ""; }} />
          <span className="drop-title">{busy ? t("start.drop.busy") : t("start.drop.title")}</span>
          <span className="drop-sub">{t("start.drop.sub")}</span>
          <span className="btn primary" aria-hidden="true">{t("start.drop.button")}</span>
        </label>
        <div className="side">
          <h2>{t("start.sample.title")}</h2>
          <p>{t("start.sample.text")}</p>
          <button className="btn secondary" onClick={onSample} disabled={busy}>{t("start.sample.button")}</button>
          <p className="fine">{t("start.privacy")}</p>
        </div>
      </div>
      {error && <div className="alert-box" role="alert"><strong>{t("start.badfile")}</strong> {error}</div>}
      <ul className="promises">
        <li><strong>{t("start.p1.title")}</strong> {t("start.p1.text")}</li>
        <li><strong>{t("start.p2.title")}</strong> {t("start.p2.text")}</li>
        <li><strong>{t("start.p3.title")}</strong> {t("start.p3.text")}</li>
      </ul>
    </>
  );
}

function Check(p: {
  dataset: DatasetSummary; error: string | null; horizon: number; calendar: string;
  setHorizon: (h: AnalysisSettings["horizon"]) => void; setCalendar: (c: AnalysisSettings["calendar"]) => void;
  onChange: (d: DatasetSummary) => void; onStart: () => void; onOther: () => void;
}) {
  const { dataset: d } = p;
  const { t, n } = useLang();
  const say = useServerText();
  const [err, setErr] = useState<string | null>(null);
  const det = d.detection;
  const cols = det.columns.map((c) => c.name);
  const remap = async (m: { date: string; value?: string | null; item?: string | null; item_columns?: string[] | null }) => {
    setErr(null);
    try { p.onChange(await api.remap(d.id, m)); } catch (e) { setErr(say(toProblem(e), "problem")); }
  };
  const tooLittle = d.plan.tier === "too_little";
  const warnings = d.report.notes.filter((x) => x.level === "warning");
  const infos = d.report.notes.filter((x) => x.level === "info");
  const planText = say({ code: d.plan.tier, params: d.plan.params, text: d.plan.text }, "plan");
  return (
    <div className="check">
      <header className="check-head">
        <p className="step muted">{t("check.step")}</p>
        <h1>{t("check.title")}</h1>
        <p className="lead small">
          {d.is_sample ? t("app.sample") : <strong>{d.filename}</strong>}: {t("check.summary", { items: n("unit.item", d.n_series), days: n("unit.day", d.n_days), first: d.first_date, last: d.last_date })}
        </p>
      </header>
      {(p.error || err) && <div className="alert-box" role="alert">{p.error ?? err}</div>}
      <div className="check-grid">
        <section className="card" aria-labelledby="cols-h">
          <h2 id="cols-h">{t("check.understood")}</h2>
          {d.is_sample ? <p className="muted">{t("check.sample.ok")}</p> : det.layout === "long" ? (
            <div className="fields">
              <Field label={t("check.field.date")} value={det.date} options={cols} onChange={(v) => remap({ date: v, value: det.value, item: det.item })} />
              <Field label={t("check.field.value")} value={det.value ?? ""} options={cols.filter((c) => c !== det.date)} onChange={(v) => remap({ date: det.date, value: v, item: det.item })} />
              <Field label={t("check.field.item")} value={det.item ?? ""} options={cols.filter((c) => c !== det.date && c !== det.value)} none={t("check.field.noitem")} onChange={(v) => remap({ date: det.date, value: det.value, item: v || null })} />
            </div>
          ) : (
            <>
              <p>{t("check.wide", { names: det.item_columns.join("، ") })}</p>
              <Field label={t("check.field.date")} value={det.date} options={cols} onChange={(v) => remap({ date: v, item_columns: det.item_columns })} />
              <button className="btn link" onClick={() => remap({ date: det.date, value: det.item_columns[0], item: null })}>{t("check.wide.switch", { name: det.item_columns[0] })}</button>
            </>
          )}
          <table className="mini" aria-label={t("check.table.label")}>
            <thead><tr><th scope="col">{t("check.table.column")}</th><th scope="col">{t("check.table.examples")}</th></tr></thead>
            <tbody>{det.columns.slice(0, 8).map((c) => <tr key={c.name}><th scope="row">{c.name}</th><td dir="auto">{c.examples.join(" · ")}</td></tr>)}</tbody>
          </table>
        </section>
        <section className="card" aria-labelledby="notes-h">
          <h2 id="notes-h">{t("check.cleaned")}</h2>
          {warnings.length === 0 && infos.length === 0 && <p className="muted">{t("check.cleaned.none")}</p>}
          {warnings.length > 0 && <ul className="notes warn">{warnings.map((x, i) => <li key={i}><span className="tag">{t("check.tag")}</span> {say(x, "note")}</li>)}</ul>}
          {infos.length > 0 && <ul className="notes">{infos.map((x, i) => <li key={i}>{say(x, "note")}</li>)}</ul>}
        </section>
        <section className={`card tier ${d.plan.tier}`} aria-labelledby="tier-h">
          <h2 id="tier-h">{t(`check.tier.${d.plan.tier}`)}</h2>
          <p>{planText}</p>
        </section>
        <section className="card" aria-labelledby="set-h">
          <h2 id="set-h">{t("check.settings")}</h2>
          <fieldset className="seg-field">
            <legend>{t("check.horizon")}</legend>
            <div className="seg" role="radiogroup">
              {[7, 14, 28].map((h) => (
                <label key={h} className={p.horizon === h ? "on" : ""}><input type="radio" name="horizon" checked={p.horizon === h} onChange={() => p.setHorizon(h as 7 | 14 | 28)} />{n("unit.day", h)}</label>
              ))}
            </div>
          </fieldset>
          <fieldset className="radios">
            <legend>{t("check.holidays")}</legend>
            <label><input type="radio" name="cal" checked={p.calendar === "none"} onChange={() => p.setCalendar("none")} /> {t("check.cal.none")}</label>
            <label><input type="radio" name="cal" checked={p.calendar === "egypt"} onChange={() => p.setCalendar("egypt")} /> {t("check.cal.egypt")}</label>
            {d.has_events && <label><input type="radio" name="cal" checked={p.calendar === "events"} onChange={() => p.setCalendar("events")} /> {t("check.cal.events")}</label>}
            <p className="fine">{t("check.cal.note")}</p>
          </fieldset>
        </section>
      </div>
      <div className="actions">
        <button className="btn primary big" onClick={p.onStart} disabled={tooLittle}>{t("check.start")}</button>
        <button className="btn link" onClick={p.onOther}>{t("check.other")}</button>
      </div>
    </div>
  );
}

function Field({ label, value, options, onChange, none }: { label: string; value: string; options: string[]; onChange: (v: string) => void; none?: string }) {
  return (
    <label className="field">
      <span>{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        {none && <option value="">{none}</option>}
        {options.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    </label>
  );
}

function Running({ job, sample, full }: { job: Job | null; sample: boolean; full: boolean }) {
  const { t } = useLang();
  const label = useMethodLabel();
  const p = job?.progress ?? 0;
  const raw = job?.message ?? "Starting";
  const m = /method '(.+)'/.exec(raw);
  const message = m ? t("run.step.method", { method: label(m[1]) }) : raw === "Scoring" ? t("run.step.score") : raw === "Starting" ? t("run.starting") : raw;
  return (
    <div className="running" role="status" aria-live="polite">
      <Mark size={44} />
      <h1>{t("run.title")}</h1>
      <p className="lead small">{message}</p>
      <div className="bar" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(p * 100)} aria-label={t("run.progress")}><span style={{ width: `${Math.max(3, p * 100)}%` }} /></div>
      <p className="muted">{t("run.done", { pct: pct(p) })} {full ? (sample ? t("run.full.sample") : t("run.full")) : t("run.simple")}</p>
    </div>
  );
}
