import { useMemo } from "react";
import type { NextView } from "../api/types";
import { useLang } from "../i18n";
import { dateLong, pct } from "../lib/format";
import { liveModel } from "../lib/models";
import { Stage } from "./Stage";

/** Recent real sales, then the forecast and its range opening past the last day, with the unknown future hatched. */
export function ForecastChart({ next, level, horizon }: { next: NextView; level: number; horizon: number }) {
  const { t } = useLang();
  const model = useMemo(() => liveModel(next), [next]);
  return (
    <div className="panel">
      <div className="panel-top">
        <div><span className="panel-kicker">{t("next.today")}</span><strong className="panel-date">{dateLong(next.last_day)}</strong></div>
        <ul className="legend" aria-label={t("replay.legend")}>
          <li><i className="sw actual" /> {t("replay.legend.actual")}</li>
          <li><i className="sw fan" /> {t("replay.legend.fan.level", { level: pct(level) })}</li>
          <li><i className="sw curtain" /> {t("replay.legend.curtain")}</li>
        </ul>
      </div>
      <Stage model={model} label={t("next.stage.label", { item: next.item === "All items" ? t("dash.chart.title") : next.item, n: horizon, date: next.last_day, level: pct(level) })} curtainText={t("stage.unknown")} level={level} />
    </div>
  );
}
