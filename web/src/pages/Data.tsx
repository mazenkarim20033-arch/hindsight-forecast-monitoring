import { useState, type DragEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api, IS_SNAPSHOT } from "../api/client";
import type { AnalysisSettings, DatasetSummary } from "../api/types";
import { useMethodLabel } from "../components/Pickers";
import { ErrorBox } from "../components/States";
import { toProblem, type Problem } from "../hooks/useAsync";
import { useLang, useServerText } from "../i18n";
import { dateLong, pct } from "../lib/format";
import { useSession } from "../state/session";

export default function Data() {
  const { dataset, job, problem, analyze, useSample, owner } = useSession();
  const { t, n } = useLang();
  const say = useServerText();
  const navigate = useNavigate();
  const [staged, setStaged] = useState<DatasetSummary | null>(null);
  const [error, setError] = useState<Problem | null>(null);
  const [busy, setBusy] = useState(false);
  const [horizon, setHorizon] = useState<AnalysisSettings["horizon"]>(28);
  const [calendar, setCalendar] = useState<AnalysisSettings["calendar"]>("none");
  const running = job?.state === "running";
  const shown = staged ?? dataset;

  async function receive(make: () => Promise<DatasetSummary>) {
    setBusy(true);
    setError(null);
    try {
      const d = await make();
      setStaged(d);
      setCalendar(d.has_events ? "events" : "none");
    } catch (e) {
      setError(toProblem(e));
    } finally {
      setBusy(false);
    }
  }

  async function run() {
    if (!staged) return;
    if (await analyze({ horizon, calendar }, staged)) { setStaged(null); navigate("/"); }
  }

  async function backToSample() {
    setStaged(null);
    if (await useSample()) navigate("/");
  }

  return (
    <>
      <header className="page-head">
        <h1>{t("data.title")}</h1>
        <p className="lede">{t("data.lede")}</p>
      </header>

      {dataset && !staged && (
        <section className="section" aria-labelledby="cur-h">
          <div className="section-head"><h2 id="cur-h">{t("data.current")}</h2><span className="chip dataset">{t("chip.dataset")}</span></div>
          <p>{dataset.is_sample ? t("data.current.sample") : t("data.current.own", { name: dataset.filename })} {t("check.summary", { items: n("unit.item", dataset.n_series), days: n("unit.day", dataset.n_days), first: dateLong(dataset.first_date), last: dateLong(dataset.last_date) })}</p>
          <p className="muted">{say({ code: dataset.plan.tier, params: dataset.plan.params, text: dataset.plan.text }, "plan")}</p>
          {!dataset.is_sample && <button onClick={backToSample} disabled={running}>{t("data.sample.button")}</button>}
        </section>
      )}

      <section className="section" aria-labelledby="load-h">
        <div className="section-head"><h2 id="load-h">{t("data.load.title")}</h2></div>
        {IS_SNAPSHOT ? <p>{t("data.demo")}</p> : owner.allowed ? (
          <>
            <Drop busy={busy || running} onFile={(f) => receive(() => api.upload(f))} />
            <p className="fine">{t("data.load.text")}</p>
          </>
        ) : <OwnerGate />}
        {error && <div className="alert-box" role="alert"><strong>{t("start.badfile")}</strong> {say(error, "problem")}</div>}
      </section>

      {staged && (
        <Check
          dataset={staged} horizon={horizon} calendar={calendar} setHorizon={setHorizon} setCalendar={setCalendar}
          onChange={setStaged} onRun={run} running={running} problem={problem} shown={shown}
        />
      )}
      {running && <Progress />}
      {!staged && problem && <ErrorBox problem={problem} />}
    </>
  );
}

function Progress() {
  const { job } = useSession();
  const { t } = useLang();
  const label = useMethodLabel();
  const p = job?.progress ?? 0;
  const raw = job?.message ?? "Starting";
  const m = /method '(.+)'/.exec(raw);
  const message = m ? t("run.step.method", { method: label(m[1]) }) : raw === "Scoring" ? t("run.step.score") : raw === "Starting" ? t("run.starting") : raw;
  return (
    <section className="section" role="status" aria-live="polite" aria-labelledby="prog-h">
      <h2 id="prog-h">{t("data.running")}</h2>
      <p>{message}</p>
      <div className="bar" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(p * 100)} aria-label={t("run.progress")}><span style={{ width: `${Math.max(3, p * 100)}%` }} /></div>
      <p className="muted">{t("run.done", { pct: pct(p) })}</p>
    </section>
  );
}

function Drop({ busy, onFile }: { busy: boolean; onFile: (f: File) => void }) {
  const { t } = useLang();
  const [over, setOver] = useState(false);
  const drop = (e: DragEvent) => {
    e.preventDefault();
    setOver(false);
    const f = e.dataTransfer.files?.[0];
    if (f) onFile(f);
  };
  return (
    <label className={`drop${over ? " over" : ""}${busy ? " busy" : ""}`} onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)} onDrop={drop}>
      <input type="file" accept=".csv,.xlsx,.xls,.txt,.tsv" disabled={busy} onChange={(e) => { const f = e.target.files?.[0]; if (f) onFile(f); e.target.value = ""; }} />
      <span className="drop-title">{busy ? t("start.drop.busy") : t("start.drop.title")}</span>
      <span className="drop-sub">{t("start.drop.sub")}</span>
      <span className="btn" aria-hidden="true">{t("start.drop.button")}</span>
    </label>
  );
}

function Check(p: {
  dataset: DatasetSummary; shown: DatasetSummary | null; horizon: number; calendar: string; running: boolean; problem: Problem | null;
  setHorizon: (h: AnalysisSettings["horizon"]) => void; setCalendar: (c: AnalysisSettings["calendar"]) => void;
  onChange: (d: DatasetSummary) => void; onRun: () => void;
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
  return (
    <section className="section" aria-labelledby="chk-h">
      <div className="section-head"><h2 id="chk-h">{d.is_sample ? t("app.sample") : d.filename}</h2><span className="chip dataset">{t("chip.dataset")}</span></div>
      <p className="muted">{t("check.summary", { items: n("unit.item", d.n_series), days: n("unit.day", d.n_days), first: d.first_date, last: d.last_date })}</p>
      {err && <div className="alert-box" role="alert">{err}</div>}
      {p.problem && <ErrorBox problem={p.problem} />}
      <div className="check-grid">
        <div className="card">
          <h3>{t("check.understood")}</h3>
          {det.layout === "long" ? (
            <>
              <Field label={t("check.field.date")} value={det.date} options={cols} onChange={(v) => remap({ date: v, value: det.value, item: det.item })} />
              <Field label={t("check.field.value")} value={det.value ?? ""} options={cols.filter((c) => c !== det.date)} onChange={(v) => remap({ date: det.date, value: v, item: det.item })} />
              <Field label={t("check.field.item")} value={det.item ?? ""} options={cols.filter((c) => c !== det.date && c !== det.value)} none={t("check.field.noitem")} onChange={(v) => remap({ date: det.date, value: det.value, item: v || null })} />
            </>
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
        </div>
        <div style={{ display: "grid", gap: "1rem" }}>
          <div className="card">
            <h3>{t("check.cleaned")}</h3>
            {warnings.length === 0 && infos.length === 0 && <p className="muted">{t("check.cleaned.none")}</p>}
            {warnings.length > 0 && <ul className="notes warn">{warnings.map((x, i) => <li key={i}><span className="tag">{t("check.tag")}</span> {say(x, "note")}</li>)}</ul>}
            {infos.length > 0 && <ul className="notes">{infos.map((x, i) => <li key={i}>{say(x, "note")}</li>)}</ul>}
          </div>
          <div className={`card tier ${d.plan.tier}`}>
            <h3>{t(`check.tier.${d.plan.tier}`)}</h3>
            <p>{say({ code: d.plan.tier, params: d.plan.params, text: d.plan.text }, "plan")}</p>
          </div>
          <div className="card">
            <h3>{t("check.settings")}</h3>
            <fieldset>
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
          </div>
        </div>
      </div>
      <div className="actions">
        <button className="primary btn big" onClick={p.onRun} disabled={tooLittle || p.running}>{t("data.run")}</button>
      </div>
    </section>
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

/** Loading data is for the owner only: with a key configured the owner types it here; without one, only the computer running the server counts. */
function OwnerGate() {
  const { owner, unlock } = useSession();
  const { t } = useLang();
  const [key, setKey] = useState("");
  const [wrong, setWrong] = useState(false);
  if (!owner.required) return <p className="note-box">{t("owner.locked")} {t("owner.local")}</p>;
  return (
    <form className="card" onSubmit={async (e) => { e.preventDefault(); setWrong(!(await unlock(key))); }}>
      <h3>{t("owner.title")}</h3>
      <p className="muted">{t("owner.locked")} {t("owner.keyed")}</p>
      <label className="field">
        <span>{t("owner.key")}</span>
        <input type="password" autoComplete="off" value={key} onChange={(e) => { setKey(e.target.value); setWrong(false); }} aria-invalid={wrong} />
      </label>
      {wrong && <p role="alert" className="bad">{t("owner.wrong")}</p>}
      <div><button className="btn primary" type="submit" disabled={!key.trim()}>{t("owner.unlock")}</button></div>
    </form>
  );
}
