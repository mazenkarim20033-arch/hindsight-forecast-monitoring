import type { Overview } from "../api/types";
import { AUTO, useSession } from "../state/session";

export function methodLabel(name: string, reference: boolean, auto: boolean): string {
  if (auto) return "Best method so far (switches to whoever is winning)";
  const nice = name === "learning model" ? "Learning model" : name.charAt(0).toUpperCase() + name.slice(1);
  return reference ? `${nice} (the simple rule to beat)` : nice;
}

export function Pickers({ overview, showLevel = true }: { overview: Overview; showLevel?: boolean }) {
  const { item, setItem, method, setMethod, level, setLevel } = useSession();
  return (
    <div className="pickers">
      {overview.series.length > 1 && (
        <label className="pick">
          <span>Item</span>
          <select value={item} onChange={(e) => setItem(e.target.value)}>
            {overview.series.map((s) => <option key={s.id} value={s.id}>{s.id}</option>)}
          </select>
        </label>
      )}
      <label className="pick">
        <span>Forecast method</span>
        <select value={method} onChange={(e) => setMethod(e.target.value)}>
          {[...overview.methods].sort((a, b) => Number(b.is_auto) - Number(a.is_auto)).map((m) => (
            <option key={m.name} value={m.is_auto ? AUTO : m.name}>{methodLabel(m.name, m.is_reference, m.is_auto)}</option>
          ))}
        </select>
      </label>
      {showLevel && (
        <fieldset className="pick seg-field">
          <legend>Range</legend>
          <div className="seg" role="radiogroup">
            {([0.8, 0.9] as const).map((l) => (
              <label key={l} className={level === l ? "on" : ""}><input type="radio" name="level" checked={level === l} onChange={() => setLevel(l)} />{l * 100}%</label>
            ))}
          </div>
        </fieldset>
      )}
    </div>
  );
}
