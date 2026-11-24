import { useState } from "react";
import { api } from "../api/client";
import type { PlanRow } from "../api/types";
import { Pickers } from "../components/Pickers";
import { ErrorBox, Loading } from "../components/States";
import { useAsync } from "../hooks/useAsync";
import { useLang } from "../i18n";
import { num, pct } from "../lib/format";
import { useSession } from "../state/session";

export default function Planner() {
  const { dataset, overview, method } = useSession();
  const { t } = useLang();
  const [item, setItem] = useState("");
  const plan = useAsync((signal) => api.planner(dataset!.id, { item: item || undefined, method }, signal), [dataset!.id, item, method]);
  const p = plan.data;
  const by = (k: PlanRow["key"]) => p?.strategies.find((s) => s.key === k);
  const guess = by("model_guess");
  const top = by("upper_90");
  return (
    <>
      <header className="page-head">
        <h1>{t("planner.title")}</h1>
        <p className="lede">{t("planner.lede")}</p>
      </header>
      {overview && <Pickers overview={overview} item={item} setItem={setItem} allLabel={t("planner.all")} showLevel={false} />}
      {plan.error && <ErrorBox problem={plan.error} onRetry={plan.reload} />}
      {!p && !plan.error && <Loading />}
      {p && guess && top && (
        <>
          <p className="headline long">
            {t("planner.summary", { short: pct(guess.stockout_share), lost: pct(guess.lost_share, 1), short90: pct(top.stockout_share), lost90: pct(top.lost_share, 1), left90: pct(top.leftover_share, 1) })}
          </p>
          <section className="section" aria-labelledby="plan-h">
            <div className="section-head"><h2 id="plan-h">{p.item === "All items" ? t("planner.all") : p.item}</h2><span className="chip evaluation">{t("chip.evaluation")}</span></div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th scope="col">{t("planner.rule")}</th>
                    <th scope="col" className="num">{t("planner.avg")}</th>
                    <th scope="col">{t("planner.short")}</th>
                    <th scope="col">{t("planner.lost")}</th>
                    <th scope="col">{t("planner.left")}</th>
                  </tr>
                </thead>
                <tbody>
                  {p.strategies.map((s) => (
                    <tr key={s.key}>
                      <th scope="row">{t(`planner.rule.${s.key}`)}</th>
                      <td className="num">{num(s.average_order)}</td>
                      <td><Meter value={s.stockout_share} tone="short" /></td>
                      <td><Meter value={s.lost_share} tone="short" digits={1} /></td>
                      <td><Meter value={s.leftover_share} tone="left" digits={1} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="muted">{t("planner.basis", { n: p.n_dates, demand: num(p.average_demand) })}</p>
            <p className="fine">{t("planner.note")}</p>
          </section>
        </>
      )}
    </>
  );
}

/** A number with a bar. The bar's length is the value; shortage and leftover differ in position and label, not just colour. */
export function Meter({ value, tone, digits = 0 }: { value: number; tone: "short" | "left"; digits?: number }) {
  return (
    <span className={`meter ${tone}`}>
      <span className="meter-track" aria-hidden="true" dir="ltr"><span style={{ width: `${Math.min(100, value * 100)}%` }} /></span>
      <span className="meter-val">{pct(value, digits)}</span>
    </span>
  );
}
