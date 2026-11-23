import type { Overview } from "../api/types";
import { useLang } from "../i18n";
import { pct } from "../lib/format";
import { AUTO, useSession } from "../state/session";

/** A method's display name in the current language. */
export function useMethodLabel() {
  const { t } = useLang();
  return (name: string, reference = false, auto = false): string => {
    if (auto) return t("method.auto");
    const nice = t(`method.${name}`);
    const shown = nice === `method.${name}` ? name.charAt(0).toUpperCase() + name.slice(1) : nice;
    return reference ? t("method.reference", { name: shown }) : shown;
  };
}

interface Props {
  overview: Overview;
  item?: string;
  setItem?: (i: string) => void;
  showLevel?: boolean;
}

export function Pickers({ overview, item, setItem, showLevel = true }: Props) {
  const { method, setMethod, level, setLevel } = useSession();
  const { t } = useLang();
  const label = useMethodLabel();
  return (
    <div className="toolbar pickers">
      {setItem && overview.series.length > 1 && (
        <label className="pick">
          <span>{t("pick.item")}</span>
          <select value={item} onChange={(e) => setItem(e.target.value)}>
            {overview.series.map((s) => <option key={s.id} value={s.id}>{s.id}</option>)}
          </select>
        </label>
      )}
      <label className="pick">
        <span>{t("pick.method")}</span>
        <select value={method} onChange={(e) => setMethod(e.target.value)}>
          {[...overview.methods].sort((a, b) => Number(b.is_auto) - Number(a.is_auto)).map((m) => (
            <option key={m.name} value={m.is_auto ? AUTO : m.name}>{label(m.name, m.is_reference, m.is_auto)}</option>
          ))}
        </select>
      </label>
      {showLevel && (
        <fieldset className="pick">
          <legend>{t("pick.range")}</legend>
          <div className="seg" role="radiogroup">
            {([0.8, 0.9] as const).map((l) => (
              <label key={l} className={level === l ? "on" : ""}><input type="radio" name="level" checked={level === l} onChange={() => setLevel(l)} />{pct(l)}</label>
            ))}
          </div>
        </fieldset>
      )}
    </div>
  );
}
