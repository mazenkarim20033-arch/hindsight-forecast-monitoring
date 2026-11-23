import { useId } from "react";
import { useWidth } from "../hooks/useSize";
import { useLang } from "../i18n";
import { dateShort, monthYear, num } from "../lib/format";
import type { StageModel } from "../lib/models";

interface Props {
  model: StageModel;
  label: string;
  onSeek?: (localDay: number) => void;
  curtainText?: string;
}

// Time runs left to right in every language, so the chart is drawn in a left-to-right box even on a right-to-left page.

const PAD = { l: 56, r: 18, t: 34, b: 66 };

function compact(v: number): string {
  return v >= 10000 ? `${Math.round(v / 1000)}k` : v >= 1000 ? `${(v / 1000).toFixed(1).replace(".0", "")}k` : String(Math.round(v));
}

/** The replay stage: real sales up to the cursor, the forecast fan opening from the day it was made, and the curtain over what is not yet known. */
export function Stage({ model, label, onSeek, curtainText }: Props) {
  const [ref, W] = useWidth<HTMLDivElement>();
  const { t } = useLang();
  const uid = useId().replace(/:/g, "");
  const H = Math.round(Math.min(440, Math.max(300, W * 0.4)));
  const { dates, actual, fan, cursor, hits, ymax } = model;
  const span = W < 560 ? 72 : 132;
  const lookback = Math.round(span * 0.72);
  const start = Math.max(0, Math.min(cursor - lookback, dates.length - span));
  const end = Math.min(dates.length - 1, start + span - 1);
  const n = end - start + 1;
  const plotW = W - PAD.l - PAD.r;
  const x = (i: number) => PAD.l + ((i - start + 0.5) / n) * plotW;
  const y = (v: number) => PAD.t + (1 - Math.min(v, ymax) / ymax) * (H - PAD.t - PAD.b);
  const laneY = H - PAD.b + 26;
  const step = plotW / n;

  const seg = (from: number, to: number, get: (i: number) => number | null) => {
    let d = "";
    let pen = false;
    for (let i = from; i <= to; i++) {
      const v = get(i);
      if (v == null) { pen = false; continue; }
      d += `${pen ? "L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)}`;
      pen = true;
    }
    return d;
  };

  const actualPath = seg(start, Math.min(cursor, end), (i) => actual[i]);
  let band = "";
  let line = "";
  if (fan) {
    const o = fan.origin;
    const pts: { i: number; f: number; lo: number | null; hi: number | null }[] = [];
    fan.forecast.forEach((f, k) => { if (f != null && o + 1 + k <= end + 40) pts.push({ i: o + 1 + k, f, lo: fan.low[k], hi: fan.high[k] }); });
    const first = actual[o];
    line = (first != null ? `M${x(o).toFixed(1)} ${y(first).toFixed(1)}` : "") + pts.map((p, k) => `${k === 0 && first == null ? "M" : "L"}${x(p.i).toFixed(1)} ${y(p.f).toFixed(1)}`).join("");
    const ranged = pts.filter((p) => p.lo != null && p.hi != null);
    if (ranged.length > 1) {
      band = `M${ranged.map((p) => `${x(p.i).toFixed(1)} ${y(p.hi as number).toFixed(1)}`).join("L")}L${[...ranged].reverse().map((p) => `${x(p.i).toFixed(1)} ${y(p.lo as number).toFixed(1)}`).join("L")}Z`;
    }
  }

  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => f * ymax);
  const months: { i: number; text: string }[] = [];
  for (let i = start; i <= end; i++) {
    const firstOfMonth = dates[i].endsWith("-01");
    const roomAtStart = i === start && !dates.slice(i + 1, i + 12).some((d) => d.endsWith("-01"));  // a month mark right next to the left edge would overlap
    if (firstOfMonth || roomAtStart) months.push({ i, text: monthYear(dates[i]) });
  }
  const curtainX = Math.min(x(cursor) + step / 2, W - PAD.r);
  const revealedFrom = fan ? Math.max(fan.origin, start) : start;

  const seek = (e: React.MouseEvent<SVGSVGElement>) => {
    if (!onSeek) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const px = ((e.clientX - rect.left) / rect.width) * W;
    const i = Math.round(((px - PAD.l) / plotW) * n - 0.5) + start;
    if (i >= 0 && i < dates.length) onSeek(i);
  };

  return (
    <div ref={ref} className="stage-canvas" dir="ltr">
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label} onClick={seek} className={onSeek ? "seekable" : undefined}>
        <defs>
          <pattern id={`pleat-${uid}`} width="12" height="12" patternUnits="userSpaceOnUse">
            <rect width="12" height="12" className="pleat-base" />
            <rect width="5" height="12" className="pleat-light" />
          </pattern>
          <linearGradient id={`fade-${uid}`} x1="0" x2="1">
            <stop offset="0" stopColor="#0F1B45" stopOpacity="0.95" />
            <stop offset="1" stopColor="#0F1B45" stopOpacity="0.8" />
          </linearGradient>
        </defs>

        {ticks.map((t) => (
          <g key={t}>
            <line className="grid" x1={PAD.l} x2={W - PAD.r} y1={y(t)} y2={y(t)} />
            <text className="axis" x={PAD.l - 10} y={y(t) + 4} textAnchor="end">{compact(t)}</text>
          </g>
        ))}
        {fan && revealedFrom < Math.min(cursor, end) && (
          <rect className="since" x={x(revealedFrom)} y={PAD.t - 8} width={Math.max(0, x(Math.min(cursor, end)) - x(revealedFrom))} height={H - PAD.t - PAD.b + 8} />
        )}

        {cursor < end && (
          <g className="curtain-lift">
            <rect x={curtainX} y={PAD.t - 14} width={W - curtainX} height={H - PAD.t - PAD.b + 14} fill={`url(#fade-${uid})`} />
            <rect x={curtainX} y={PAD.t - 14} width={W - curtainX} height={H - PAD.t - PAD.b + 14} fill={`url(#pleat-${uid})`} opacity="0.55" />
            <line className="curtain-edge" x1={curtainX} x2={curtainX} y1={PAD.t - 14} y2={H - PAD.b} />
          </g>
        )}

        {band && <path className="fan-band" d={band} />}
        {line && <path className="fan-line" d={line} />}
        {actualPath && <path className="actual-line" d={actualPath} />}
        {cursor >= start && cursor <= end && actual[cursor] != null && <circle className="actual-dot" cx={x(cursor)} cy={y(actual[cursor] as number)} r={4.2} />}

        {fan && fan.origin >= start && fan.origin <= end && (
          <g>
            <line className="today" x1={x(fan.origin)} x2={x(fan.origin)} y1={PAD.t - 12} y2={H - PAD.b} />
            <text className="today-label" x={x(fan.origin) + (x(fan.origin) > W - 190 ? -8 : 8)} y={PAD.t - 16} textAnchor={x(fan.origin) > W - 190 ? "end" : "start"}>
              {model.live ? t("stage.today") : t("stage.made", { date: dateShort(dates[fan.origin]) })}
            </text>
          </g>
        )}
        {curtainText && curtainX < W - PAD.r - 150 && (
          <text className="curtain-text" x={W - PAD.r - 12} y={H - PAD.b - 14} textAnchor="end">{curtainText}</text>
        )}

        {hits && <g>
          <text className="lane-label" x={PAD.l - 10} y={laneY - 2} textAnchor="end">{t("stage.held")}</text>
          <text className="lane-label" x={PAD.l - 10} y={laneY + 14} textAnchor="end">{t("stage.missed")}</text>
          <line className="lane" x1={PAD.l} x2={W - PAD.r} y1={laneY + 5} y2={laneY + 5} />
          {Array.from({ length: Math.max(0, Math.min(cursor, end) - start + 1) }, (_, k) => start + k).map((i) => {
            const h = hits?.[i];
            if (h == null) return null;
            const fresh = fan ? i > fan.origin : false;
            const cx = x(i);
            return h
              ? <circle key={i} className={`hit${fresh ? " fresh" : ""}`} cx={cx} cy={laneY - 4} r={Math.min(2.6, Math.max(1.3, step * 0.42))} />
              : <path key={i} className={`miss${fresh ? " fresh" : ""}`} d={`M${cx - 2.4} ${laneY + 9}l4.8 4.8M${cx + 2.4} ${laneY + 9}l-4.8 4.8`} />;
          })}
        </g>}

        <g>
          {months.map((m) => (
            <text key={`m${m.i}`} className="axis" x={x(m.i)} y={H - 8} textAnchor={m.i === start ? "start" : "middle"}>{m.text}</text>
          ))}
        </g>
        {W >= 560 && <text className="axis-title" x={PAD.l - 10} y={14} textAnchor="start">{t("stage.axis", { max: num(ymax) })}</text>}
      </svg>
    </div>
  );
}
