"""Does a target service level hold on the replayed past of the M5 sample?

For several cover periods and service levels, order up to the quantile of earlier actual-to-forecast ratios (only periods finished by then)
and count how often demand stayed within it. 'Realized' near 'target' means the empirical demand picture is sound for these data. It says
nothing about money (the sample has no prices or costs) and nothing about future periods. Writes reports/inventory_m5.md."""
from pathlib import Path

from hindsight.app import inventory_service as inv
from hindsight.app import service
from hindsight.app.api import CACHE_DIR, load_sample

ROOT = Path(__file__).resolve().parents[1]
LEVELS = {"80%": 0.80, "90%": 0.90, "95%": 0.95, "98%": 0.98}


def main() -> None:
    data, _, _ = load_sample()
    a = service.run_analysis(data, service.Settings(horizon=28, calendar="events"), cache_dir=CACHE_DIR)
    lines = ["# Service-level check on the M5 sample", "",
             f"{a.data.n_series} stores, {a.data.n_days} days, method '{service.AUTO}', {int(a.in_window[: a.n_real].sum())} scored replay dates per store.", "",
             "| Cover period (days) | Target | Realized | Cases |", "|---|---|---|---|"]
    for days in (3, 7, 10, 14, 21, 28):
        for row in inv.calibration(a, service.AUTO, days, LEVELS):
            lines.append(f"| {days} | {row['target']:.0%} | {row['realized']:.1%} | {row['n_cases']} |")
    lines += ["", "Cases overlap in time (neighbouring replay dates share days), so small gaps are within noise. Store-level data only: item-level files with many zero days were not checked."]
    out = ROOT / "reports" / "inventory_m5.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
