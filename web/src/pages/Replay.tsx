import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { Overview, Stage as StageData } from "../api/types";
import { Check, Cross } from "../components/Mark";
import { Pickers } from "../components/Pickers";
import { Ribbon } from "../components/Ribbon";
import { ErrorBox, Loading } from "../components/States";
import { Stage } from "../components/Stage";
import { useVerdictText } from "../components/verdict";
import { useAsync } from "../hooks/useAsync";
import { SPEEDS, usePlayer } from "../hooks/usePlayer";
import { useLang } from "../i18n";
import { dateLong, num, pct } from "../lib/format";
import { firstDay, heldSoFar, lastDay, readoutAt, replayModel, stageYMax } from "../lib/models";
import { useSession } from "../state/session";

export default function Replay() {
  const { dataset, overview } = useSession();
  if (!dataset || !overview) return null;
  return <ReplayInner id={dataset.id} overview={overview} />;
}

function ReplayInner({ id, overview }: { id: string; overview: Overview }) {
  const { method, level } = useSession();
  const { t } = useLang();
  const [item, setItem] = useState(overview.series[0]?.id);
  const stage = useAsync((signal) => api.stage(id, { item, method, level }, signal), [id, item, method, level]);
  return (
    <>
      <header className="page-head">
        <h1>{t("replay.title")}</h1>
        <p className="lede">{t("replay.lead")}</p>
      </header>
      <Pickers overview={overview} item={item} setItem={setItem} />
      {stage.error && <ErrorBox problem={stage.error} onRetry={stage.reload} />}
      {!stage.data && !stage.error && <Loading text={t("replay.loading")} />}
      {stage.data && <Player stage={stage.data} overview={overview} loading={stage.loading} />}
    </>
  );
}
function Player({ stage, overview, loading }: { stage: StageData; overview: Overview; loading: boolean }) {
  const { t, n } = useLang();
  const verdictText = useVerdictText();
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
      const el = e.target as HTMLElement;
      if (["INPUT", "SELECT", "TEXTAREA", "BUTTON"].includes(el.tagName) || e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.key === " ") { e.preventDefault(); toggle(); }
      else if (e.key === "ArrowRight") { e.preventDefault(); step(e.shiftKey ? 7 : 1); } // arrows follow the chart, where time runs left to right
      else if (e.key === "ArrowLeft") { e.preventDefault(); step(e.shiftKey ? -7 : -1); }
      else if (e.key === "Home") { e.preventDefault(); seek(min); }
      else if (e.key === "End") { e.preventDefault(); seek(max); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [toggle, step, seek, min, max]);

  const date = stage.dates[player.value - stage.first_day];
  const label = t("replay.stage.label", { item: stage.item, date });
  const rangeRow = out && out.low != null && out.high != null;
  const verdict = verdictText(overview.verdict);
  const saidVars = out ? { made: dateLong(out.madeOn), ahead: n("unit.day", out.daysAhead), low: num(out.low), high: num(out.high), guess: num(out.forecast) } : undefined;
  return (
    <div className="lab" aria-busy={loading}>
      <div className="panel" data-testid="stage">
        <div className="panel-top">
          <div>
            <span className="panel-kicker">{t("replay.showing")}</span>
            <strong className="panel-date">{dateLong(date)}</strong>
          </div>
          <ul className="legend" aria-label={t("replay.legend")}>
            <li><i className="sw actual" /> {t("replay.legend.actual")}</li>
            <li><i className="sw fan" /> {t("replay.legend.fan")}</li>
            <li><i className="sw curtain" /> {t("replay.legend.curtain")}</li>
          </ul>
        </div>
        <Stage model={model} label={label} onSeek={seekLocal} curtainText={t("stage.hidden")} />
        <div className="transport">
          <div className="buttons" role="group" aria-label={t("replay.playback")} dir="ltr">
            <button className="icon-btn" onClick={() => player.seek(min)} aria-label={t("replay.start")} title={t("replay.start")}><Skip /></button>
            <button className="icon-btn" onClick={() => player.step(-1)} aria-label={t("replay.back")} title={t("replay.back")}><Step dir={-1} /></button>
            <button className="play" onClick={player.toggle} aria-label={player.playing ? t("replay.pause") : t("replay.play")} title={player.playing ? t("replay.pause") : t("replay.play")}>{player.playing ? <Pause /> : <Play />}</button>
            <button className="icon-btn" onClick={() => player.step(1)} aria-label={t("replay.forward")} title={t("replay.forward")}><Step dir={1} /></button>
          </div>
          <div className="speed" role="group" aria-label={t("replay.speed")} dir="ltr">
            {SPEEDS.map((s, i) => <button key={s.label} aria-pressed={player.speed === i} className={player.speed === i ? "on" : ""} onClick={() => player.setSpeed(i)}>{s.label}</button>)}
          </div>
          <p className="hint">{t("replay.hint")}</p>
        </div>
        <Ribbon hits={stage.ribbon.hit} dates={stage.dates} cursor={player.value - stage.first_day} min={min - stage.first_day} max={max - stage.first_day} onSeek={seekLocal} />
        <p className="ribbon-legend"><span className="k hit"><Check size={12} /> {t("replay.ribbon.held")}</span> <span className="k miss"><Cross size={12} /> {t("replay.ribbon.missed")}</span> <span className="k none">{t("replay.ribbon.none")}</span></p>
      </div>

      <div className="readouts" aria-live={player.playing ? "off" : "polite"}>
        <article className="readout day">
          <h2>{t("replay.day.title")}</h2>
          {out ? (
            <>
              <p className="said">{rangeRow ? t("replay.day.said.range", saidVars) : t("replay.day.said.point", saidVars)}</p>
              <p className="sold">{t("replay.day.sold")} <strong className="actual-num">{num(out.actual)}</strong></p>
              {out.hit != null ? (
                <p className={`result ${out.hit ? "ok" : "bad"}`}>{out.hit ? <><Check /> {t("replay.day.inside")}</> : <><Cross /> {t("replay.day.outside")}</>}</p>
              ) : <p className="result none">{t("replay.day.norange")}</p>}
            </>
          ) : <p className="muted">{t("replay.day.empty")}</p>}
        </article>
        <article className="readout trust">
          <h2>{t("replay.trust.title")}</h2>
          <p className="big-number" data-testid="held">{held.of ? pct(held.held / held.of) : "–"}</p>
          <p>{t("replay.trust.text", { level: pct(stage.level), held: num(held.held), of: num(held.of) })}</p>
        </article>
        <article className="readout verdict-mini">
          <h2>{t("replay.verdict.title")}</h2>
          <p>{verdict.text}</p>
          <Link className="btn secondary" to="/scorecard">{t("replay.verdict.open")}</Link>
        </article>
      </div>
    </div>
  );
}

const Play = () => <svg width="22" height="22" viewBox="0 0 22 22" aria-hidden="true"><path d="M6 3.5v15l13-7.5z" fill="currentColor" /></svg>;
const Pause = () => <svg width="22" height="22" viewBox="0 0 22 22" aria-hidden="true"><path d="M5.5 3.5h4.2v15H5.5zM12.3 3.5h4.2v15h-4.2z" fill="currentColor" /></svg>;
const Skip = () => <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true"><path d="M3.5 3v12M15 3v12L6 9z" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" strokeLinecap="round" /></svg>;
const Step = ({ dir }: { dir: 1 | -1 }) => <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true" style={{ transform: dir === -1 ? "scaleX(-1)" : undefined }}><path d="M5 3l7 6-7 6z" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" /></svg>;
