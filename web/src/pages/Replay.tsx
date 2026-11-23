import { useEffect, useMemo } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { Overview, Stage as StageData } from "../api/types";
import { Check, Cross } from "../components/Mark";
import { Pickers } from "../components/Pickers";
import { Ribbon } from "../components/Ribbon";
import { ErrorBox, Loading } from "../components/States";
import { Stage } from "../components/Stage";
import { useAsync } from "../hooks/useAsync";
import { SPEEDS, usePlayer } from "../hooks/usePlayer";
import { dateLong, num, pct, plural } from "../lib/format";
import { firstDay, heldSoFar, lastDay, readoutAt, replayModel, stageYMax } from "../lib/models";
import { useSession } from "../state/session";

export default function Replay() {
  const { dataset, overview } = useSession();
  if (!dataset || !overview) return <NoFile />;
  return <ReplayInner id={dataset.id} overview={overview} />;
}

function ReplayInner({ id, overview }: { id: string; overview: Overview }) {
  const { item, method, level } = useSession();
  const stage = useAsync((signal) => api.stage(id, { item, method, level }, signal), [id, item, method, level]);
  return (
    <section className="page replay">
      <header className="page-head">
        <h1>Replay</h1>
        <p className="lead small">Press play to watch the past again. At each date the forecast sees only what was known then; the curtain lifts as the real days arrive.</p>
      </header>
      <Pickers overview={overview} />
      {stage.error && <ErrorBox message={stage.error} onRetry={stage.reload} />}
      {!stage.data && !stage.error && <Loading text="Loading the replay" />}
      {stage.data && <Player stage={stage.data} overview={overview} loading={stage.loading} />}
    </section>
  );
}

export function NoFile() {
  return (
    <section className="page narrow">
      <h1>No file yet</h1>
      <p className="lead small">Load a sales file first, then come back here to replay it.</p>
      <Link className="btn primary" to="/">Choose a file</Link>
    </section>
  );
}

function Player({ stage, overview, loading }: { stage: StageData; overview: Overview; loading: boolean }) {
  const min = firstDay(stage);
  const max = lastDay(stage);
  const player = usePlayer(min, max, min + Math.round((max - min) * 0.25));
  const ymax = useMemo(() => stageYMax(stage), [stage]);
  const model = useMemo(() => replayModel(stage, player.value, ymax), [stage, player.value, ymax]);
  const out = readoutAt(stage, player.value);
  const held = heldSoFar(stage, player.value);
  const seekLocal = (i: number) => player.seek(i + stage.first_day);
  const toggle = player.toggle;
  const step = player.step;
  const seek = player.seek;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (["INPUT", "SELECT", "TEXTAREA", "BUTTON"].includes(t.tagName) || e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.key === " ") { e.preventDefault(); toggle(); }
      else if (e.key === "ArrowRight") { e.preventDefault(); step(e.shiftKey ? 7 : 1); }
      else if (e.key === "ArrowLeft") { e.preventDefault(); step(e.shiftKey ? -7 : -1); }
      else if (e.key === "Home") { e.preventDefault(); seek(min); }
      else if (e.key === "End") { e.preventDefault(); seek(max); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [toggle, step, seek, min, max]);

  const date = stage.dates[player.value - stage.first_day];
  const label = `Replay stage for ${stage.item}. Real sales up to ${date}, with the forecast made on the latest replay date and the range it gave. The future is hidden.`;
  const rangeRow = out && out.low != null && out.high != null;
  return (
    <div className={`stage-panel${loading ? " refreshing" : ""}`}>
      <div className="stage" data-testid="stage">
        <div className="stage-top">
          <div>
            <span className="stage-kicker">Showing</span>
            <strong className="stage-date">{dateLong(date)}</strong>
          </div>
          <Legend />
        </div>
        <Stage model={model} label={label} onSeek={seekLocal} curtainText="Not yet revealed" />
        <div className="transport">
          <div className="buttons" role="group" aria-label="Playback">
            <button className="icon-btn" onClick={() => player.seek(min)} aria-label="Back to the start" title="Back to the start (Home)"><Skip /></button>
            <button className="icon-btn" onClick={() => player.step(-1)} aria-label="Back one day" title="Back one day (←)"><Step dir={-1} /></button>
            <button className="play" onClick={player.toggle} aria-label={player.playing ? "Pause" : "Play"} title={`${player.playing ? "Pause" : "Play"} (space)`}>{player.playing ? <Pause /> : <Play />}</button>
            <button className="icon-btn" onClick={() => player.step(1)} aria-label="Forward one day" title="Forward one day (→)"><Step dir={1} /></button>
          </div>
          <div className="speed" role="group" aria-label="Speed">
            {SPEEDS.map((s, i) => <button key={s.label} aria-pressed={player.speed === i} className={player.speed === i ? "on" : ""} onClick={() => player.setSpeed(i)}>{s.label}</button>)}
          </div>
          <p className="hint">Space plays · arrows step a day · shift+arrows step a week</p>
        </div>
        <Ribbon hits={stage.ribbon.hit} dates={stage.dates} cursor={player.value - stage.first_day} min={min - stage.first_day} max={max - stage.first_day} onSeek={seekLocal} />
        <p className="ribbon-legend"><span className="k hit"><Check size={12} /> range held</span> <span className="k miss"><Cross size={12} /> real sales fell outside it</span> <span className="k none">blank: no range yet</span></p>
      </div>

      <div className="readouts" aria-live={player.playing ? "off" : "polite"}>
        <article className="readout day">
          <h2>On this day</h2>
          {out ? (
            <>
              <p className="said">The forecast made on {dateLong(out.madeOn)}, {plural(out.daysAhead, "day")} earlier, said <strong>{rangeRow ? `${num(out.low)} to ${num(out.high)}` : `about ${num(out.forecast)}`}</strong>{rangeRow ? ` (best guess ${num(out.forecast)})` : ""}.</p>
              <p className="sold">Real sales: <strong className="actual">{num(out.actual)}</strong></p>
              {out.hit != null ? (
                <p className={`result ${out.hit ? "ok" : "bad"}`}>{out.hit ? <><Check /> Inside the range</> : <><Cross /> Outside the range</>}</p>
              ) : <p className="result none">No range yet: not enough track record.</p>}
            </>
          ) : <p className="muted">Pick a later date to see a forecast and what happened.</p>}
        </article>
        <article className="readout trust">
          <h2>How much to trust the range</h2>
          <p className="big-number" data-testid="held">{held.of ? pct(held.held / held.of) : "n/a"}</p>
          <p>of days so far landed inside the {pct(stage.level)} range ({num(held.held)} of {num(held.of)}). A trustworthy range should land close to {pct(stage.level)}.</p>
        </article>
        <article className="readout verdict-mini">
          <h2>Is it better than a simple rule?</h2>
          <p>{overview.verdict.text}</p>
          <Link className="btn secondary" to="/scorecard">Open the scorecard</Link>
        </article>
      </div>
    </div>
  );
}

function Legend() {
  return (
    <ul className="legend" aria-label="Chart key">
      <li><i className="sw actual" /> Real sales</li>
      <li><i className="sw fan" /> Forecast and its range</li>
      <li><i className="sw curtain" /> Not yet known</li>
    </ul>
  );
}

const Play = () => <svg width="22" height="22" viewBox="0 0 22 22" aria-hidden="true"><path d="M6 3.5v15l13-7.5z" fill="currentColor" /></svg>;
const Pause = () => <svg width="22" height="22" viewBox="0 0 22 22" aria-hidden="true"><path d="M5.5 3.5h4.2v15H5.5zM12.3 3.5h4.2v15h-4.2z" fill="currentColor" /></svg>;
const Skip = () => <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true"><path d="M3.5 3v12M15 3v12L6 9z" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" strokeLinecap="round" /></svg>;
const Step = ({ dir }: { dir: 1 | -1 }) => <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true" style={{ transform: dir === -1 ? "scaleX(-1)" : undefined }}><path d="M5 3l7 6-7 6z" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" /></svg>;
