"""Record the app's answers for the bundled sample as static JSON, so the public demo needs no server.

Every file is exactly what the live API returns for that request (same service functions), recorded once. The demo can therefore only show
numbers the real code produced; it cannot be asked anything else. Writes to web/public/snapshot/."""
import json
import re
import shutil
from pathlib import Path

from hindsight.app import service
from hindsight.app.api import CACHE_DIR, SAMPLE_DIR, _describe, load_sample
from hindsight.data.importer import read_sales_file

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "web" / "public" / "snapshot"
METHODS = [service.AUTO, "learning model", service.REFERENCE]
LEVELS = [0.8, 0.9]


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def write(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    data, rep, det = load_sample()
    a = service.run_analysis(data, service.Settings(horizon=28, calendar="events"), cache_dir=CACHE_DIR)
    d = a.data
    plan = service.plan_for(d.n_days, 28)
    write(OUT / "dataset.json", {"id": "snapshot", "filename": "Sample: 10 Walmart stores (public M5 data)", "is_sample": True, "report": rep, "detection": det,
                                 "n_series": d.n_series, "n_days": d.n_days, "first_date": str(d.dates[0].date()), "last_date": str(d.dates[-1].date()),
                                 "has_events": True, "analyzed": True, "plan": {"tier": plan.tier, "text": plan.explanation, "params": plan.params}})
    write(OUT / "effects.json", service.holiday_effects(a.data))
    ov = service.overview(a)
    ov["methods"] = [m for m in ov["methods"] if m["name"] in METHODS]
    write(OUT / "overview.json", ov)
    sc = service.scorecard(a)
    sc["methods"] = [m for m in sc["methods"] if m["method"] in METHODS or m["method"] == service.REFERENCE]
    write(OUT / "scorecard.json", sc)
    for method in METHODS:
        write(OUT / "alerts" / f"{slug(method)}.json", service.alerts(a, method))
        write(OUT / "dashboard" / f"{slug(method)}.json", service.dashboard(a, method))
        write(OUT / "planner" / f"{slug(method)}__all.json", service.stock_plan(a, None, method))
        for level in LEVELS:
            write(OUT / "total" / f"{slug(method)}__{int(level * 100)}.json", service.total_next(a, method, level))
        for item in d.ids:
            write(OUT / "alerts" / f"{slug(method)}__{item}.json", service.alerts(a, method, item=item))
            write(OUT / "planner" / f"{slug(method)}__{item}.json", service.stock_plan(a, item, method))
            reasons_all = None  # the reasons do not depend on the range level, so work them out once per item and method
            for level in LEVELS:
                write(OUT / "stage" / f"{item}__{slug(method)}__{int(level * 100)}.json", service.stage(a, item, method, level))
                nxt = service.next_view(a, item, method, level, 0)
                if nxt["reasons"]:
                    if reasons_all is None:
                        reasons_all = [nxt["reasons"]] + [service.next_view(a, item, method, level, day)["reasons"] for day in range(1, a.settings.horizon)]
                    nxt["reasons_all"] = reasons_all
                write(OUT / "next" / f"{item}__{slug(method)}__{int(level * 100)}.json", nxt)
    size = sum(f.stat().st_size for f in OUT.rglob("*.json"))
    print(f"{len(list(OUT.rglob('*.json')))} files, {size / 1e6:.1f} MB -> {OUT}")


if __name__ == "__main__":
    main()
