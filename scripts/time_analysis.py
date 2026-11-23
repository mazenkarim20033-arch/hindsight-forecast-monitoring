"""Time a full app analysis on the bundled sample, phase by phase, so slow spots are measured rather than guessed."""
import cProfile
import pstats
import time

from hindsight.app import service
from hindsight.app.api import load_sample


def main() -> None:
    data, _, _ = load_sample()
    t0 = time.perf_counter()
    marks = []
    prof = cProfile.Profile()
    prof.enable()
    service.run_analysis(data, service.Settings(horizon=28, calendar="events"), lambda p, m: marks.append((time.perf_counter() - t0, p, m)))
    prof.disable()
    total = time.perf_counter() - t0
    scoring_from = next(t for t, p, m in marks if m == "Scoring")
    print(f"total {total:.1f}s; replaying {scoring_from:.1f}s; ranges and scoring {total - scoring_from:.1f}s")
    pstats.Stats(prof).sort_stats("cumulative").print_stats(14)


if __name__ == "__main__":
    main()
