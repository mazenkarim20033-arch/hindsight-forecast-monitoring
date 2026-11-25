"""How often does the health monitor fire, and does it notice a real change? Writes reports/health_m5.md.

A. M5 sample, every 5th day of the last two years: the share of item-days in each status, using only what was known on each day.
   M5 has no known "broken" periods, so these are shares of alarms, not proven false alarms.
B. Synthetic data with a level change injected on a known day (weekly pattern plus noise, 12 seeds each): days until the changed item leaves
   "healthy" and "action", and how often an unchanged series raises "watch" or "action".
C. Why drift does not change the status: on M5, how often the PSI limit is crossed while accuracy is healthy."""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from test_health import analyse, synth  # noqa: E402

from hindsight.app import health_service, service  # noqa: E402
from hindsight.app.api import CACHE_DIR, load_sample  # noqa: E402
from hindsight.monitoring.rules import Thresholds  # noqa: E402


def share(xs: list[str]) -> dict[str, float]:
    return {k: round(xs.count(k) / len(xs), 3) for k in ("healthy", "watch", "action", "unknown")}


def main() -> None:
    lines = ["# Forecast health: how the rules behave", ""]
    data, _, _ = load_sample()
    a = service.run_analysis(data, service.Settings(horizon=28, calendar="events"), cache_dir=CACHE_DIR)
    days = list(range(a.data.n_days - 730, a.data.n_days, 5))
    fixed_only = Thresholds(z_watch=-1e9, z_action=-1e9)  # the fixed limits alone, as the monitor first worked
    status, status_fixed, drift_flags, both = [], [], 0, 0
    for day in days:
        now = health_service.health(a, day=day)["items"]
        old = health_service.health(a, T=fixed_only, day=day)["items"]
        status += [i["status"] for i in now]
        status_fixed += [i["status"] for i in old]
        for i in now:
            psi = next(s for s in i["signals"] if s["key"] == "drift")["value"]
            if psi is not None and psi > 0.25:
                drift_flags += 1
                both += i["status"] == "healthy"
    lines += ["## A. M5 sample (100 items, every 5th day of the last 730 days, method: best method so far)", "",
              f"Item-days checked: {len(status)}.", "",
              f"- Current rule (past the fixed limit AND unusual for that item): {share(status)}",
              f"- Fixed limits alone (how the monitor first worked): {share(status_fixed)}", "",
              "On single items the fixed limits fired on about half of all item-days, because item-level sales are noisy; judging each signal against that item's own earlier "
              "ups and downs is the change made after seeing that. M5 has no known broken period, so these are shares of alarms, not proven false alarms.", "",
              "## C. Demand drift on the same item-days", "",
              f"PSI above the conventional 0.25 limit on {drift_flags} of {len(status)} item-days ({drift_flags / len(status):.0%}); on {both} of those ({both / max(drift_flags, 1):.0%}) the status from error-based signals was healthy. "
              "Drift is shown but does not set the status.", ""]

    for label, factor in (("sales rise 50%", 1.5), ("sales fall 30%", 0.7)):
        first_any, first_act, missed = [], [], 0
        for seed in range(12):
            an = analyse(synth(640, shift_at=480, factor=factor, seed=seed))
            sts = [health_service.health(an, day=d)["items"][0]["status"] for d in range(480, 600)]
            fa = next((i for i, s in enumerate(sts) if s != "healthy"), None)
            fx = next((i for i, s in enumerate(sts) if s == "action"), None)
            missed += fa is None
            first_any.append(fa)
            first_act.append(fx)
        got, act = [x for x in first_any if x is not None], [x for x in first_act if x is not None]
        lines += [f"## B. Injected change: {label} on day 480 of 640", "",
                  f"Seeds: 12. Missed entirely: {missed}. Days until the item left 'healthy': median {np.median(got):.0f}, worst {max(got)}. "
                  f"'Action' reached in {len(act)} of 12 seeds (median {np.median(act):.0f} days)." if act else f"Seeds: 12. Missed entirely: {missed}. Median days until not healthy: {np.median(got):.0f}. 'Action' never reached.", ""]
    quiet = []
    for seed in range(12):
        an = analyse(synth(700, seed=100 + seed))
        quiet += [i["status"] for d in range(300, 690, 5) for i in health_service.health(an, day=d)["items"]]
    lines += ["## B. Unchanged synthetic series (12 seeds, every 5th day from day 300)", "", f"Item-days: {len(quiet)}. Shares: {share(quiet)}", "",
              "Caveat: synthetic data is easier than real sales. These numbers say the rules can notice a clear change and stay mostly quiet otherwise; they do not promise the same on a real shop.", ""]
    out = ROOT / "reports" / "health_m5.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
