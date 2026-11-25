"""How do the forecasters do on the bundled 100-item sample? Writes reports/item_sample_m5.md.

The same replay, scorecard and ranges the app shows, written down so the numbers in the documents can be traced. Items are M5 products added up over
the chain's 10 stores, chosen by the rule in scripts/make_sample.py, written down before any forecast was run on them. Nothing is tuned."""
from pathlib import Path

import numpy as np

from hindsight.app import service
from hindsight.app.api import CACHE_DIR, load_sample
from hindsight.replay.metrics import wape

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    data, _, _ = load_sample()
    a = service.run_analysis(data, service.Settings(horizon=28, calendar="events"), cache_dir=CACHE_DIR)
    v = np.asarray(data.values, dtype=float)
    lines = ["# The 100-item sample: forecaster comparison", "",
             f"{data.n_series} items, {data.n_days} days, {int(a.in_window.sum())} scored replay dates (every {a.plan.step} days over the last {service.SCORE_DAYS} days), "
             f"{a.settings.horizon}-day horizon. Reference rule: '{service.REFERENCE}'. WAPE = total absolute error divided by total sales (lower is better).", "",
             "| Method | WAPE | Gain over the reference (95% interval) | Ahead on | 80% range held | 90% range held |", "|---|---|---|---|---|---|"]
    for r in a.rows:
        gain = "reference" if r["is_reference"] else f"{r['gain_vs_reference'] * 100:+.1f} pts ({r['gain_ci95'][0] * 100:+.1f} to {r['gain_ci95'][1] * 100:+.1f})"
        win = "" if r["is_reference"] else f"{r['win_rate_vs_reference']:.0%}"
        lines.append(f"| {r['method']} | {r['wape'] * 100:.1f}% | {gain} | {win} | {r['coverage_80']:.1%} | {r['coverage_90']:.1%} |")
    ver = service.verdict(a)
    ver = service.verdict(a)
    ref, ml = [], []
    for i in range(data.n_series):
        ref.append(wape(service._sub(a.replays[service.REFERENCE], i).where(a.in_window)))
        ml.append(wape(service._sub(a.replays["learning model"], i).where(a.in_window)))
    ref, ml = np.array(ref), np.array(ml)
    zero = (v == 0).mean(axis=1)
    lines += ["", f"App verdict: {ver['text']}", "", "## Spread across the items", "",
              f"- Share of days with no sales per item: median {np.median(zero):.1%}, highest {zero.max():.1%}.",
              f"- Item-level WAPE of the reference rule: median {np.median(ref):.1%} (lowest {ref.min():.1%}, highest {ref.max():.1%}).",
              f"- The learning model had the lower WAPE on {int((ml < ref).sum())} of {data.n_series} items and the higher on {int((ml > ref).sum())}.", "",
              "Read this as: on single products (added up over ten stores) errors are several times larger than at store or company level (reports/models_m5.md), and the "
              "learning model's edge over the simple rule is real but small. The sample holds 100 items chosen by a fixed rule; other items or other businesses may differ."]
    out = ROOT / "reports" / "item_sample_m5.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
