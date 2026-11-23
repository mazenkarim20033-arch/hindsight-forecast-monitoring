import { useEffect, useRef, useState, type DragEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { AnalysisSettings, DatasetSummary, Job } from "../api/types";
import { Mark } from "../components/Mark";
import { num, pct } from "../lib/format";
import { useSession } from "../state/session";

type Phase = "choose" | "check" | "running";

export default function Start() {
  const { dataset, setDataset, setOverview, restoring } = useSession();
  const [phase, setPhase] = useState<Phase>("choose");
  const [error, setError] = useState<string | null>(null);
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

  const fail = (e: unknown) => setError(e instanceof ApiError ? e.message : String(e));

  async function receive(make: () => Promise<DatasetSummary>) {
    setBusy(true);
    setError(null);
    try {
      const d = await make();
      setDataset(d);
      setCalendar(d.has_events ? "events" : "none");
      setPhase("check");
    } catch (e) {
      fail(e);
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
      fail(e);
    }
  }

  function poll(id: string) {
    timer.current = window.setTimeout(async () => {
      try {
        const j = await api.job(id);
        setJob(j);
        if (j.state === "running") return poll(id);
        if (j.state === "failed") { setError(j.error ?? "The replay stopped unexpectedly."); setPhase("check"); return; }
        if (dataset) {
          setOverview(await api.overview(dataset.id));
          setDataset({ ...dataset, analyzed: true });
          navigate("/replay");
        }
      } catch (e) {
        fail(e);
        setPhase("check");
      }
    }, 500);
  }

  if (restoring) return <section className="page narrow"><p className="muted" role="status">Looking for your last file…</p></section>;

  return (
    <section className="page start">
      {phase === "choose" && <Choose busy={busy} error={error} onFile={(f) => receive(() => api.upload(f))} onSample={() => receive(() => api.sample())} />}
      {phase === "check" && dataset && (
        <Check
          dataset={dataset} error={error} horizon={horizon} calendar={calendar}
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
        <Mark size={44} />
        <h1>See how far to trust a forecast before you rely on it.</h1>
        <p className="lead">Hindsight replays your own sales history. For every past day it shows what the forecast would have said, using only what was known then, next to what really happened.</p>
      </div>
      <div className="start-grid">
        <label className={`drop${over ? " over" : ""}${busy ? " busy" : ""}`} onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)} onDrop={drop}>
          <input type="file" accept=".csv,.xlsx,.xls,.txt,.tsv" disabled={busy} onChange={(e) => { const f = e.target.files?.[0]; if (f) onFile(f); e.target.value = ""; }} />
          <span className="drop-title">{busy ? "Reading your file…" : "Drop your sales file here"}</span>
          <span className="drop-sub">or choose a file. Excel or CSV, one row per day (or per receipt). Arabic and English headers both work.</span>
          <span className="btn primary" aria-hidden="true">Choose a file</span>
        </label>
        <div className="side">
          <h2>No file to hand?</h2>
          <p>Try the replay on real sales from 10 Walmart stores over five years (public M5 data, US).</p>
          <button className="btn secondary" onClick={onSample} disabled={busy}>Use the sample data</button>
          <p className="fine">Your file is read by the Hindsight server running on this computer. It is kept in memory only and is not sent anywhere else.</p>
        </div>
      </div>
      {error && <div className="alert-box" role="alert"><strong>This file could not be used.</strong> {error}</div>}
      <ul className="promises">
        <li><strong>Honest by design.</strong> The forecast never sees the day it is predicting.</li>
        <li><strong>A track record, not a promise.</strong> Every range says how often it held.</li>
        <li><strong>The simple rule is always in the race.</strong> If it wins, Hindsight says so.</li>
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
  const [err, setErr] = useState<string | null>(null);
  const det = d.detection;
  const cols = det.columns.map((c) => c.name);
  const remap = async (m: { date: string; value?: string | null; item?: string | null; item_columns?: string[] | null }) => {
    setErr(null);
    try { p.onChange(await api.remap(d.id, m)); } catch (e) { setErr(e instanceof ApiError ? e.message : String(e)); }
  };
  const tooLittle = d.plan.tier === "too_little";
  const warnings = d.report.notes.filter((n) => n.level === "warning");
  const infos = d.report.notes.filter((n) => n.level === "info");
  return (
    <div className="check">
      <header className="check-head">
        <p className="eyebrow-less muted">Step 1 of 2</p>
        <h1>Is this your data?</h1>
        <p className="lead small">{d.is_sample ? d.filename : <><strong>{d.filename}</strong></>}: {num(d.n_series)} {d.n_series === 1 ? "item" : "items"}, {num(d.n_days)} days, from {d.first_date} to {d.last_date}.</p>
      </header>
      {(p.error || err) && <div className="alert-box" role="alert">{p.error ?? err}</div>}
      <div className="check-grid">
        <section className="card" aria-labelledby="cols-h">
          <h2 id="cols-h">What Hindsight understood</h2>
          {d.is_sample ? <p className="muted">The sample is already in the right shape.</p> : det.layout === "long" ? (
            <div className="fields">
              <Field label="Date column" value={det.date} options={cols} onChange={(v) => remap({ date: v, value: det.value, item: det.item })} />
              <Field label="Sales column" value={det.value ?? ""} options={cols.filter((c) => c !== det.date)} onChange={(v) => remap({ date: det.date, value: v, item: det.item })} />
              <Field label="Item column" value={det.item ?? ""} options={cols.filter((c) => c !== det.date && c !== det.value)} none="No item column: treat everything as one item" onChange={(v) => remap({ date: det.date, value: det.value, item: v || null })} />
            </div>
          ) : (
            <>
              <p>Each column is an item: <strong>{det.item_columns.join(", ")}</strong>.</p>
              <Field label="Date column" value={det.date} options={cols} onChange={(v) => remap({ date: v, item_columns: det.item_columns })} />
              <button className="btn link" onClick={() => remap({ date: det.date, value: det.item_columns[0], item: null })}>Use just “{det.item_columns[0]}” as the sales column instead</button>
            </>
          )}
          <table className="mini" aria-label="Columns in your file">
            <thead><tr><th scope="col">Column</th><th scope="col">Examples</th></tr></thead>
            <tbody>{det.columns.slice(0, 8).map((c) => <tr key={c.name}><th scope="row">{c.name}</th><td>{c.examples.join(" · ")}</td></tr>)}</tbody>
          </table>
        </section>
        <section className="card" aria-labelledby="notes-h">
          <h2 id="notes-h">What was cleaned</h2>
          {warnings.length === 0 && infos.length === 0 && <p className="muted">Nothing needed fixing.</p>}
          {warnings.length > 0 && <ul className="notes warn">{warnings.map((n, i) => <li key={i}><span className="tag">Check</span> {n.text}</li>)}</ul>}
          {infos.length > 0 && <ul className="notes">{infos.map((n, i) => <li key={i}>{n.text}</li>)}</ul>}
        </section>
        <section className={`card tier ${d.plan.tier}`} aria-labelledby="tier-h">
          <h2 id="tier-h">{tooLittle ? "Not enough history yet" : d.plan.tier === "simple" ? "Enough for simple rules" : "Enough for the full comparison"}</h2>
          <p>{d.plan.text}</p>
        </section>
        <section className="card" aria-labelledby="set-h">
          <h2 id="set-h">Settings</h2>
          <fieldset className="seg-field">
            <legend>How far ahead should it forecast?</legend>
            <div className="seg" role="radiogroup">
              {[7, 14, 28].map((h) => (
                <label key={h} className={p.horizon === h ? "on" : ""}><input type="radio" name="horizon" checked={p.horizon === h} onChange={() => p.setHorizon(h as 7 | 14 | 28)} />{h} days</label>
              ))}
            </div>
          </fieldset>
          <fieldset className="radios">
            <legend>Holidays</legend>
            <label><input type="radio" name="cal" checked={p.calendar === "none"} onChange={() => p.setCalendar("none")} /> Do not use a holiday calendar</label>
            <label><input type="radio" name="cal" checked={p.calendar === "egypt"} onChange={() => p.setCalendar("egypt")} /> Egyptian holidays: Ramadan, Eids, Coptic Christmas, Sham el-Nessim, national days</label>
            {d.has_events && <label><input type="radio" name="cal" checked={p.calendar === "events"} onChange={() => p.setCalendar("events")} /> The events listed with this sample (US holidays)</label>}
            <p className="fine">Whether a holiday calendar helps depends on your shop. Run the replay both ways and compare the scorecards; Hindsight does not assume it helps. The learning model only runs on two years or more of history.</p>
          </fieldset>
        </section>
      </div>
      <div className="actions">
        <button className="btn primary big" onClick={p.onStart} disabled={tooLittle}>Start the replay</button>
        <button className="btn link" onClick={p.onOther}>Use a different file</button>
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
  const p = job?.progress ?? 0;
  return (
    <div className="running" role="status" aria-live="polite">
      <Mark size={44} />
      <h1>Replaying your past</h1>
      <p className="lead small">{job?.message ?? "Starting"}</p>
      <div className="bar" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(p * 100)} aria-label="Replay progress"><span style={{ width: `${Math.max(3, p * 100)}%` }} /></div>
      <p className="muted">{pct(p)} done. {full ? (sample ? "The learning model trains again every few weeks of replay, so this takes about a minute." : "Training a learning model on each past date can take a minute or two.") : "This takes a few seconds."}</p>
    </div>
  );
}
