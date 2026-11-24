"""Checks on the cleaned daily sales: things that are legal but suspicious, with the items and dates to look at. Reports only, never changes data.

The importer already says what it changed (summed receipts, filled empty days, zeroed negatives). This looks at what is left: items that
stopped selling, a file that ends early, spikes far outside an item's normal range, items that are almost always zero. Each finding has a
`code` (so the screen can say it in the current language), a level, the item names concerned and a few examples."""
import numpy as np

from hindsight.data.sales import SalesData

STOP_DAYS = 28  # an item with no sales for this long at the end has probably stopped
LATE_START_DAYS = 90
MOSTLY_ZERO = 0.6  # share of days with no sales, counted from the item's first sale
SPIKE_MADS = 8.0  # a day this many robust deviations above the item's usual non-zero level
SPIKE_MIN_RATIO = 3.0  # and at least this many times that level
MAX_NAMES = 6


def _finding(code: str, level: str, items: list[str], **params) -> dict:
    return {"code": code, "level": level, "n_items": len(items), "items": items[:MAX_NAMES], "params": params}


def assess(data: SalesData) -> list[dict]:
    v = np.asarray(data.values, dtype=float)
    n_items, n_days = v.shape
    out: list[dict] = []
    if n_days >= 7 and not v[:, -7:].any():
        out.append(_finding("file_ends_early", "warning", [], days=7, last=str(data.dates[-1].date())))  # every item is zero for the last week
    stopped, late, sparse, constant = [], [], [], []
    spikes: list[dict] = []
    spike_items: list[str] = []
    for i, name in enumerate(data.ids):
        row = v[i]
        nz = np.flatnonzero(row > 0)
        if nz.size == 0:
            continue
        first = int(nz[0])
        if n_days >= 7 and n_days - 1 - int(nz[-1]) >= STOP_DAYS and v[:, -7:].any():
            stopped.append(name)
        if first > LATE_START_DAYS:
            late.append(name)
        active = row[first:]
        if len(active) >= 56 and float((active == 0).mean()) >= MOSTLY_ZERO:
            sparse.append(name)
        pos = row[row > 0]
        if len(pos) >= 28 and np.unique(pos).size == 1:
            constant.append(name)
        if len(pos) >= 28:
            med = float(np.median(pos))
            mad = float(np.median(np.abs(pos - med))) * 1.4826
            if mad > 0:
                hit = np.flatnonzero((row > med + SPIKE_MADS * mad) & (row > SPIKE_MIN_RATIO * med))
                if hit.size:
                    spike_items.append(name)
                    spikes += [{"item": name, "date": str(data.dates[d].date()), "value": float(row[d]), "usual": round(med, 2)} for d in hit[:2]]
    if stopped:
        out.append(_finding("stopped_selling", "warning", stopped, days=STOP_DAYS))
    if late:
        out.append(_finding("late_start", "info", late, days=LATE_START_DAYS))
    if sparse:
        out.append(_finding("mostly_zero", "warning", sparse, share=MOSTLY_ZERO))
    if constant:
        out.append(_finding("constant_values", "info", constant))
    if spike_items:
        f = _finding("spikes", "warning", spike_items, n_days=len(spikes))
        f["examples"] = sorted(spikes, key=lambda s: -s["value"] / max(s["usual"], 1e-9))[:5]
        out.append(f)
    return out
