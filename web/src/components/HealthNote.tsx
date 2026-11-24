import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { HealthStatus } from "../api/types";
import { useAsync } from "../hooks/useAsync";
import { useLang } from "../i18n";
import { Status } from "../pages/Health";
import { useSession } from "../state/session";

/** The forecast's health as of the last day of data, for pages whose advice rests on the forecast. Nothing is shown while it loads or if it cannot be had. */
function useHealthStatus(): HealthStatus | null {
  const { dataset, method } = useSession();
  const res = useAsync((signal) => api.health(dataset!.id, method, signal), [dataset!.id, method]);
  return res.data?.overall?.status ?? null;
}

/** On the dashboard: one line saying whether the forecast is still doing as well as it did, with the ways on. */
export function HealthSection() {
  const { t } = useLang();
  const status = useHealthStatus();
  if (!status) return null;
  return (
    <section className="section" aria-labelledby="dash-health-h">
      <div className="section-head"><h2 id="dash-health-h">{t("dash.health.title")}</h2><span className="chip evaluation">{t("chip.evaluation")}</span></div>
      <p className="health-big"><Status s={status} /></p>
      <p>{t(`health.status.${status}.text`)}</p>
      <p className="toolbar">
        <Link className="btn" to="/health">{t("dash.health.open")}</Link>
        <Link className="btn" to="/inventory">{t("dash.health.plan")}</Link>
      </p>
    </section>
  );
}

/** On the order screen: a caution when the forecast behind the advice is not healthy. */
export function HealthCaution() {
  const { t } = useLang();
  const status = useHealthStatus();
  if (status !== "watch" && status !== "action") return null;
  return <p className="note-box" role="note"><Status s={status} /> {t(`inv.health.${status}`)} <Link to="/health">{t("nav.health")}</Link></p>;
}
