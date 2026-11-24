import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { InventoryInputs, InventoryItem, ScenarioSpec, StrategyKey } from "../api/types";
import { toProblem } from "../hooks/useAsync";
import { useLang, useServerText } from "../i18n";
import { num } from "../lib/format";
import { useSession } from "../state/session";

/** Writes the current recommendation, what was actually ordered and why, to the decision log. The server works the numbers out again; nothing here is trusted. */
export default function RecordDecision({ body, items, strategy, scenario }: { body: InventoryInputs; items: InventoryItem[]; strategy: StrategyKey; scenario?: ScenarioSpec }) {
  const { t } = useLang();
  const say = useServerText();
  const { dataset, owner } = useSession();
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState("");
  const [over, setOver] = useState<Record<string, string>>({});
  const [state, setState] = useState<{ busy: boolean; error: string | null; id: number | null }>({ busy: false, error: null, id: null });
  if (!owner.allowed) return null;
  const rows = items.filter((i) => i.status === "ok" && i.by_strategy[strategy]);

  const save = async () => {
    setState({ busy: true, error: null, id: null });
    const orders: Record<string, number> = {};
    for (const [k, v] of Object.entries(over)) { const x = Number(v.replace(",", ".")); if (v.trim() !== "" && Number.isFinite(x)) orders[k] = x; }
    try {
      const ev = await api.auditRecord(dataset!.id, { ...body, strategy, orders, note, ...(scenario ? { scenario } : {}) });
      setState({ busy: false, error: null, id: ev.id });
      setNote(""); setOver({}); setOpen(false);
    } catch (e) { setState({ busy: false, error: say(toProblem(e), "problem"), id: null }); }
  };

  return (
    <div className="card" style={{ marginTop: "1rem" }}>
      <h3>{t("rec.title")}</h3>
      <p className="fine">{scenario ? t("rec.lede.scenario", { name: scenario.name }) : t("rec.lede")}</p>
      {state.id != null && <p role="status" className="note-box">{t("rec.saved", { id: state.id })} <Link to="/audit">{t("rec.open")}</Link></p>}
      {state.error && <p role="alert" className="alert-box">{state.error}</p>}
      {!open ? <p><button className="btn" onClick={() => setOpen(true)}>{t("rec.start")}</button></p> : (
        <>
          <p className="fine">{t("rec.option", { option: t(`inv.strategy.${strategy}`) })}</p>
          <details>
            <summary>{t("rec.override")}</summary>
            <div className="table-wrap" tabIndex={0} role="region" aria-label={t("rec.override")}>
              <table>
                <thead><tr><th scope="col">{t("score.items.item")}</th><th scope="col" className="num">{t("rec.recommended")}</th><th scope="col" className="num">{t("rec.ordered")}</th></tr></thead>
                <tbody>
                  {rows.map((i) => (
                    <tr key={i.item}>
                      <th scope="row">{i.item}</th>
                      <td className="num">{num(i.by_strategy[strategy]!.order)}</td>
                      <td className="num"><input className="cell" type="text" inputMode="decimal" aria-label={`${i.item}: ${t("rec.ordered")}`} placeholder={num(i.by_strategy[strategy]!.order)} value={over[i.item] ?? ""} onChange={(e) => setOver((o) => ({ ...o, [i.item]: e.target.value }))} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
          <label className="field"><span>{t("rec.note")}</span><textarea rows={3} maxLength={500} value={note} onChange={(e) => setNote(e.target.value)} /></label>
          <p>
            <button className="btn primary" onClick={save} disabled={state.busy}>{t("rec.save")}</button>{" "}
            <button className="btn link" onClick={() => setOpen(false)}>{t("rec.cancel")}</button>
          </p>
          <p className="fine">{t("rec.fine")}</p>
        </>
      )}
    </div>
  );
}
