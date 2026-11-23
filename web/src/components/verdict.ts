import type { Verdict } from "../api/types";
import { useLang } from "../i18n";
import { pct, signedPoints } from "../lib/format";
import { useMethodLabel } from "./Pickers";

/** The verdict sentences, built from the numbers so they read the same in every language. */
export function useVerdictText() {
  const { t } = useLang();
  const label = useMethodLabel();
  return (v: Verdict) => {
    const params = { method: label(v.method), wape: pct(v.wape, 1), ref: pct(v.reference_wape, 1), win: pct(v.win_rate) };
    return {
      title: t(`verdict.${v.kind}`),
      text: t(`verdict.${v.kind}.text`, params),
      gain: v.kind === "beats" && v.gain_ci95 ? t("verdict.gain", { gain: signedPoints(v.gain), low: signedPoints(v.gain_ci95[0]), high: signedPoints(v.gain_ci95[1]) }) : null,
    };
  };
}
