"""Choosing the method that has been doing best lately, using only outcomes known at the time of the choice."""
from dataclasses import dataclass

import numpy as np

from hindsight.replay.engine import Replay


@dataclass
class Selection:
    replay: Replay
    chosen: list[str]  # the method used at each replay date


def select_online(replays: dict[str, Replay], default: str, window: int = 8) -> Selection:
    """At each replay date pick the method with the lowest WAPE over its last `window` replay dates whose entire
    forecast horizon had already been observed. Before any such date exists, use `default`."""
    names = list(replays)
    ref = replays[default]
    o, s, h = ref.forecasts.shape
    for r in replays.values():
        if not np.array_equal(r.origins, ref.origins) or r.forecasts.shape != ref.forecasts.shape:
            raise ValueError("all replays must cover the same dates and series")
    err = {n: np.abs(r.forecasts - r.actuals).sum(axis=(1, 2)) for n, r in replays.items()}
    tot = ref.actuals.sum(axis=(1, 2))
    forecasts = np.empty_like(ref.forecasts)
    chosen = []
    for i in range(o):
        known = np.where(ref.origins + h <= ref.origins[i])[0][-window:]
        if len(known) == 0 or tot[known].sum() <= 0:
            pick = default
        else:
            pick = min(names, key=lambda n: err[n][known].sum() / tot[known].sum())
        chosen.append(pick)
        forecasts[i] = replays[pick].forecasts[i]
    combined = Replay("best method so far", h, ref.origins, forecasts, ref.actuals, ref.dates, ref.ids)
    return Selection(combined, chosen)
