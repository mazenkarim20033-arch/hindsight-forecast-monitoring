# Hindsight: honest forecast replay

Upload your sales history, press play, and watch what a forecast would have said at every point in the past, against what really happened. Every replay date uses only the data known at that time, so you can see how far to trust the next forecast.

**Status: Milestone 5 of 6 (polish, English and Arabic, performance).** Arabic text is not yet reviewed by a native speaker; see [docs/APP_NOTES.md](docs/APP_NOTES.md) for what was and was not checked. There is no interface yet. Plan: [docs/PROJECT_PLAN.md](docs/PROJECT_PLAN.md); design direction: [docs/DESIGN_BRIEF.md](docs/DESIGN_BRIEF.md); results so far: [docs/EXPERIMENTS.md](docs/EXPERIMENTS.md).

## What exists
- A validated sales data model (any daily series, aggregated by store, category and so on).
- A loader for the public M5 Walmart data.
- A rolling-origin replay engine: at each past date it hands a forecaster only the earlier days, then reveals what happened. Tests change the future and check earlier forecasts do not move.
- Four baseline forecasters and honest metrics (WAPE, bias, MASE, bootstrap intervals).
- Results of the baselines on M5 at six levels, from the whole company down to single items.
- Plain-language reasons for each forecast (exact tree contributions that add up to the number) and odd-day alerts, with measured catch and false-alarm rates on M5: injected closures and halvings were caught, subtle +30% days mostly were not.
- A global gradient-boosting forecaster, exponential smoothing, an Egyptian calendar (Ramadan, Eids, Coptic Christmas, Sham el-Nessim, national days), honest ranges learned from the forecaster's own track record, and "best method so far" selection. On M5 boosting beats the best simple rule by 2 to 3 WAPE points at every level; the Egyptian calendar is only shown to work on labelled synthetic data.

- A file importer (CSV or Excel; Arabic or English headers, Arabic digits, day-first dates, one row per receipt) that reports everything it guessed or changed, a local API, and a web app with Start, Replay (the "curtain" stage), Scorecard and Next week screens. The app picks methods by how much history there is: under 120 days it asks for more, under 2 years simple rules only, otherwise it adds the learning model and compares it with the simple rule.

## Run the app
```bash
pip install -e ".[api,dev]"
python -m uvicorn hindsight.app.api:app --port 8100
cd web && npm install && npm run dev      # then open http://localhost:5174
```
Use "Use the sample data" on the start page to try it without a file (the 10 Walmart stores in `data/sample/`, real M5 data). The first replay on the sample takes about a minute; it is then cached and reloads in under a second. The interface is in English and Arabic (right-to-left); the button at the top right switches.

## Setup
```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
# download the M5 zip (48 MB, CC BY 4.0) from https://zenodo.org/records/12636070 and extract it into data/raw/extracted/
python -m pytest -q
python scripts/eda_m5.py
python scripts/run_baselines.py
```

## Limits
All results so far are on US retail data and use only trivial baselines. Nothing is claimed about Egyptian shops yet. See [docs/DATASET_CARD.md](docs/DATASET_CARD.md).

Data: M5 Forecasting competition data (Walmart), via Zenodo, CC BY 4.0.
