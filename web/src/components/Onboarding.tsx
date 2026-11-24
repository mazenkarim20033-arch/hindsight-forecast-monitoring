import { useState } from "react";
import { api, type RemapBody } from "../api/client";
import type { BusinessKind, DatasetSummary, QualityFinding } from "../api/types";
import { toProblem } from "../hooks/useAsync";
import { useLang, useServerText } from "../i18n";
import { num } from "../lib/format";
import { useSession } from "../state/session";

const KINDS: BusinessKind[] = ["price", "unit_cost", "on_hand", "on_order"];

/** What the file carries beyond dates and sales: how items are named, copied rows, price/cost/stock columns, and a saved way of reading this kind of file. */
export function OnboardingChoices({ d, remap, onChange, setErr }: { d: DatasetSummary; remap: (m: RemapBody) => Promise<void>; onChange: (d: DatasetSummary) => void; setErr: (e: string | null) => void }) {
  const { t } = useLang();
  const say = useServerText();
  const { owner } = useSession();
  const det = d.detection;
  const business = det.business ?? {};
  const itemCols = det.item_cols ?? [];
  const [name, setName] = useState("");
  const [saved, setSaved] = useState<string | null>(null);
  const textCols = det.columns.filter((c) => c.name !== det.date && c.name !== det.value && c.numeric_share < 0.5 && !Object.values(business).includes(c.name)).map((c) => c.name);
  const chosen = itemCols.length ? itemCols : det.item ? [det.item] : [];
  const copies = d.report.notes.some((x) => x.code === "exact_duplicates" || x.code === "duplicates_dropped");
  const found = KINDS.filter((k) => business[k]);

  const toggle = (col: string) => {
    const next = chosen.includes(col) ? chosen.filter((c) => c !== col) : [...chosen, col];
    if (next.length >= 2) void remap({ value: det.value, item_cols: next });
    else void remap({ value: det.value, item: next[0] ?? null, item_cols: null });
  };
  const save = async () => {
    setErr(null); setSaved(null);
    try { onChange(await api.saveAdapter(d.id, { name: name.trim() })); setSaved(name.trim()); setName(""); } catch (e) { setErr(say(toProblem(e), "problem")); }
  };

  return (
    <>
      {det.layout === "long" && textCols.length >= 2 && (
        <fieldset className="card" style={{ marginTop: "1rem" }}>
          <legend>{t("onb.key")}</legend>
          <p className="fine">{t("onb.key.lede")}</p>
          {textCols.map((c) => <label key={c} className="check-row"><input type="checkbox" checked={chosen.includes(c)} onChange={() => toggle(c)} /> {c}</label>)}
        </fieldset>
      )}
      {copies && det.layout === "long" && (
        <fieldset className="card radios" style={{ marginTop: "1rem" }}>
          <legend>{t("onb.dup")}</legend>
          <label><input type="radio" name="dup" checked={(det.duplicates ?? "sum") === "sum"} onChange={() => void remap({ value: det.value, item: det.item, duplicates: "sum" })} /> {t("onb.dup.sum")}</label>
          <label><input type="radio" name="dup" checked={det.duplicates === "drop_exact"} onChange={() => void remap({ value: det.value, item: det.item, duplicates: "drop_exact" })} /> {t("onb.dup.drop")}</label>
        </fieldset>
      )}
      {found.length > 0 && (
        <p className="note-box" style={{ marginTop: "1rem" }}>{t("onb.business", { list: found.map((k) => `${t(`onb.kind.${k}`)} (${business[k]})`).join(t("onb.sep")) })}</p>
      )}
      {d.adapter && (
        <p className="note-box" style={{ marginTop: "1rem" }}>
          {d.adapter.applied ? t("onb.adapter.applied", { name: d.adapter.name }) : t("onb.adapter.fits", { name: d.adapter.name })}
          {d.adapter.description && <small className="muted" style={{ display: "block" }}>{d.adapter.description}</small>}
          {!d.adapter.applied && <> <button className="btn" onClick={() => void remap({ adapter: d.adapter!.name })}>{t("onb.adapter.apply")}</button></>}
        </p>
      )}
      {!d.is_sample && owner.allowed && (
        <div className="card" style={{ marginTop: "1rem" }}>
          <h3>{t("onb.adapter.save")}</h3>
          <p className="fine">{t("onb.adapter.save.lede")}</p>
          <label className="field"><span>{t("onb.adapter.name")}</span><input type="text" value={name} placeholder="my-weekly-export" onChange={(e) => setName(e.target.value)} /></label>
          <p><button className="btn" onClick={save} disabled={!name.trim()}>{t("onb.adapter.savebtn")}</button> {saved && <span role="status" className="muted">{t("onb.adapter.saved", { name: saved })}</span>}</p>
        </div>
      )}
    </>
  );
}

function quality(f: QualityFinding, t: (k: string, p?: Record<string, string | number>) => string): string {
  const items = f.items.join(t("onb.sep")) + (f.n_items > f.items.length ? ` +${f.n_items - f.items.length}` : "");
  const p = Object.fromEntries(Object.entries(f.params).map(([k, v]) => [k, typeof v === "number" ? v : String(v)]));
  return t(`quality.${f.code}`, { ...p, items, n: f.n_items, share: typeof f.params.share === "number" ? `${Math.round(f.params.share * 100)}%` : "" });
}

export function QualityCard({ findings }: { findings: QualityFinding[] }) {
  const { t } = useLang();
  return (
    <div className="card">
      <h3>{t("quality.title")}</h3>
      {findings.length === 0 ? <p className="muted">{t("quality.none")}</p> : (
        <ul className="notes">
          {findings.map((f) => (
            <li key={f.code}>
              {f.level === "warning" && <span className="tag">{t("check.tag")}</span>} {quality(f, t)}
              {f.examples && <small className="muted" style={{ display: "block" }}>{f.examples.map((e) => `${e.item}, ${e.date}: ${num(e.value)} (${t("quality.usual", { v: num(e.usual, 1) })})`).join(" · ")}</small>}
            </li>
          ))}
        </ul>
      )}
      <p className="fine">{t("quality.note")}</p>
    </div>
  );
}
