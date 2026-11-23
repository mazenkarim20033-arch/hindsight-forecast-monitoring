import { useWidth } from "../hooks/useSize";
import { useLang } from "../i18n";
import { dateLong } from "../lib/format";

interface Props {
  hits: (boolean | null)[];
  dates: string[];
  cursor: number; // local day index
  min: number;
  max: number;
  onSeek: (localDay: number) => void;
}

/** The whole track record in one strip: a short teal bar above the line where the range held, a coral bar below it where it did not.
 *  Time runs left to right in every language, like the chart above it. */
export function Ribbon({ hits, dates, cursor, min, max, onSeek }: Props) {
  const [ref, W] = useWidth<HTMLDivElement>(800);
  const { t } = useLang();
  const H = 54;
  const n = hits.length;
  const step = W / n;
  const x = (i: number) => i * step;
  const mid = 26;
  return (
    <div className="ribbon" ref={ref} dir="ltr">
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} aria-hidden="true" focusable="false">
        <line className="lane" x1={0} x2={W} y1={mid} y2={mid} />
        {hits.map((h, i) => {
          if (h == null) return null;
          const shown = i <= cursor;
          const w = Math.max(1, step - 0.6);
          return h
            ? <rect key={i} className={`rb-hit${shown ? "" : " dim"}`} x={x(i)} y={mid - 14} width={w} height={12} />
            : <rect key={i} className={`rb-miss${shown ? "" : " dim"}`} x={x(i)} y={mid + 2} width={w} height={12} />;
        })}
        <rect className="rb-future" x={x(cursor + 1)} y={0} width={Math.max(0, W - x(cursor + 1))} height={H} />
        <line className="rb-head" x1={x(cursor) + step / 2} x2={x(cursor) + step / 2} y1={2} y2={H - 2} />
      </svg>
      <input
        type="range" min={min} max={max} step={1} value={Math.min(Math.max(cursor, min), max)}
        aria-label={t("replay.ribbon.date")} aria-valuetext={dates[cursor] ? dateLong(dates[cursor]) : undefined}
        onChange={(e) => onSeek(Number(e.target.value))}
      />
    </div>
  );
}
