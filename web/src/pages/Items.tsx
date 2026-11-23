import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { ErrorBox, Loading } from "../components/States";
import { useAsync } from "../hooks/useAsync";
import { useLang } from "../i18n";
import { num, pct } from "../lib/format";
import { useSession } from "../state/session";
import { ChangeCell, ItemStatus } from "./Dashboard";

type Sort = "change" | "volume" | "name";

export default function Items() {
  const { dataset, method } = useSession();
  const { t } = useLang();
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<Sort>("change");
  const dash = useAsync((signal) => api.dashboard(dataset!.id, { method }, signal), [dataset!.id, method]);
  const rows = useMemo(() => {
    const items = (dash.data?.items ?? []).filter((i) => i.id.toLowerCase().includes(query.trim().toLowerCase()));
    return items.sort((a, b) => sort === "name" ? a.id.localeCompare(b.id) : sort === "volume" ? b.average_per_day - a.average_per_day : Math.abs(b.change ?? 0) - Math.abs(a.change ?? 0));
  }, [dash.data, query, sort]);
  return (
    <>
      <header className="page-head">
        <h1>{t("items.title")}</h1>
        <p className="lede">{t("items.lede")}</p>
      </header>
      <div className="toolbar">
        <label className="pick"><span>{t("items.search")}</span><input type="search" value={query} onChange={(e) => setQuery(e.target.value)} /></label>
        <label className="pick"><span>{t("items.sort")}</span>
          <select value={sort} onChange={(e) => setSort(e.target.value as Sort)}>
            <option value="change">{t("items.sort.change")}</option><option value="volume">{t("items.sort.volume")}</option><option value="name">{t("items.sort.name")}</option>
          </select>
        </label>
      </div>
      {dash.error && <ErrorBox problem={dash.error} onRetry={dash.reload} />}
      {!dash.data && !dash.error && <Loading />}
      {dash.data && (
        <>
          <div className="table-wrap">
            <table>
              <thead><tr>
                <th scope="col">{t("items.col.item")}</th><th scope="col" className="num">{t("items.col.last")}</th><th scope="col" className="num">{t("items.col.next")}</th>
                <th scope="col" className="num">{t("items.col.change")}</th><th scope="col" className="num">{t("items.col.miss")}</th><th scope="col">{t("items.col.status")}</th>
              </tr></thead>
              <tbody>
                {rows.map((it) => (
                  <tr key={it.id}>
                    <th scope="row"><Link className="tbl-link" to={`/items/${encodeURIComponent(it.id)}`}>{it.id}</Link></th>
                    <td className="num">{num(it.last_7)}</td><td className="num">{num(it.next_7)}</td>
                    <td className="num"><ChangeCell c={it.change} /></td>
                    <td className="num">{pct(it.best_wape, 1)}</td>
                    <td><ItemStatus n={it.unusual_30d} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {rows.length === 0 ? <p className="state">{t("items.empty")}</p> : <p className="pager">{t("items.count", { shown: rows.length, total: dash.data.items.length })}</p>}
        </>
      )}
    </>
  );
}
