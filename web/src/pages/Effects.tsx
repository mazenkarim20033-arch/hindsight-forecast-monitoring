import { api } from "../api/client";
import type { Effect } from "../api/types";
import { ErrorBox, Loading } from "../components/States";
import { useAsync } from "../hooks/useAsync";
import { useLang } from "../i18n";
import { pct } from "../lib/format";
import { useSession } from "../state/session";

function change(r: number): string {
  const d = r - 1;
  return `${d > 0 ? "+" : d < 0 ? "−" : ""}${pct(Math.abs(d), 0)}`;
}

export default function Effects() {
  const { dataset } = useSession();
  const { t } = useLang();
  const eff = useAsync((signal) => api.effects(dataset!.id, signal), [dataset!.id]);
  const list = eff.data?.effects ?? [];
  const egypt = list.filter((e) => e.kind === "egypt");
  const events = list.filter((e) => e.kind === "event");
  return (
    <>
      <header className="page-head">
        <h1>{t("effects.title")}</h1>
        <p className="lede">{t("effects.lede")}</p>
      </header>
      {dataset?.is_sample && <p className="note-box">{t("effects.sample")}</p>}
      {eff.error && <ErrorBox problem={eff.error} onRetry={eff.reload} />}
      {!eff.data && !eff.error && <Loading />}
      {eff.data && (
        <>
          <Group title={t("effects.egypt")} rows={egypt} label={(e) => t(`effect.${e.name}`)} />
          {events.length > 0 && <Group title={t("effects.events")} rows={events} label={(e) => e.name.replace(/([a-z])([A-Z])/g, "$1 $2")} />}
          <p className="fine">{t("effects.method")}</p>
        </>
      )}
    </>
  );
}

function Group({ title, rows, label }: { title: string; rows: Effect[]; label: (e: Effect) => string }) {
  const { t } = useLang();
  const span = Math.max(0.3, ...rows.map((r) => Math.max(Math.abs(r.ratio_high - 1), Math.abs(r.ratio_low - 1))));
  const pos = (r: number) => `${50 + ((r - 1) / span) * 50}%`; // 0 change sits in the middle
  return (
    <section className="section" aria-labelledby={`g-${title}`}>
      <div className="section-head"><h2 id={`g-${title}`}>{title}</h2><span className="chip evaluation">{t("chip.evaluation")}</span></div>
      <div className="table-wrap">
        <table>
          <thead><tr><th scope="col">{t("effects.col.name")}</th><th scope="col" className="num">{t("effects.col.change")}</th><th scope="col">{t("effects.col.range")}</th><th scope="col">{t("effects.col.times")}</th></tr></thead>
          <tbody>
            {rows.map((e) => {
              const up = e.ratio_low > 1;
              const down = e.ratio_high < 1;
              return (
                <tr key={e.name}>
                  <th scope="row">{label(e)}</th>
                  <td className="num"><span className={up ? "good" : down ? "bad" : ""}>{change(e.ratio)}</span> <span className="ci">{up ? t("effects.clear.up") : down ? t("effects.clear.down") : t("effects.unclear")}</span></td>
                  <td>
                    <span className="effect-track" dir="ltr" role="img" aria-label={`${change(e.ratio_low)} / ${change(e.ratio_high)}`}>
                      <span className="effect-zero" />
                      <span className="effect-range" style={{ left: pos(e.ratio_low), width: `calc(${pos(e.ratio_high)} - ${pos(e.ratio_low)})` }} />
                      <span className={`effect-dot ${up ? "up" : down ? "down" : ""}`} style={{ left: pos(e.ratio) }} />
                    </span>
                  </td>
                  <td>{t("effects.times", { days: e.n_days, times: e.n_occurrences })}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
