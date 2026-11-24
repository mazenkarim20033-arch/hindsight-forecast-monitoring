# Hindsight: sales forecast monitoring with an honest track record

A dashboard that forecasts the next days of sales per item, with ranges whose track record is measured, plain-language reasons for each forecast, and alerts for unusual days. A replay lab shows what the forecast would have said at every point in the past, using only what was known then, so you can see how far to trust the next one.

**Status: Milestone 6 of 6 (demo and write-up built locally; nothing published).** Read the [case study](docs/CASE_STUDY.md) first. What was and was not checked: [docs/APP_NOTES.md](docs/APP_NOTES.md). Plan: [docs/PROJECT_PLAN.md](docs/PROJECT_PLAN.md); results: [docs/EXPERIMENTS.md](docs/EXPERIMENTS.md). The Arabic text is not yet reviewed by a native speaker.

## What exists
- A validated sales data model (any daily series, aggregated by store, category and so on).
- A loader for the public M5 Walmart data.
- A rolling-origin replay engine: at each past date it hands a forecaster only the earlier days, then reveals what happened. Tests change the future and check earlier forecasts do not move.
- Four baseline forecasters and honest metrics (WAPE, bias, MASE, bootstrap intervals).
- Results of the baselines on M5 at six levels, from the whole company down to single items.
- Plain-language reasons for each forecast (exact tree contributions that add up to the number) and odd-day alerts, with measured catch and false-alarm rates on M5: injected closures and halvings were caught, subtle +30% days mostly were not.
- A global gradient-boosting forecaster, exponential smoothing, an Egyptian calendar (Ramadan, Eids, Coptic Christmas, Sham el-Nessim, national days), honest ranges learned from the forecaster's own track record, and "best method so far" selection. On M5 boosting beats the best simple rule by 2 to 3 WAPE points at every level; the Egyptian calendar is only shown to work on labelled synthetic data.

- A file importer (CSV or Excel; Arabic or English headers, Arabic digits, day-first dates, one row per receipt) that reports everything it guessed or changed, a local API, and a web app in the same technical-editorial style as SENTINEL: a Dashboard (headline, key numbers, all-items forecast, items to look at, recent unusual days), Items and an item page (forecast, reasons, unusual days), the Replay lab (the "curtain"), the Scorecard, and a Data page for loading your own file. The app opens on the bundled sample, never on an upload screen. The app picks methods by how much history there is: under 120 days it asks for more, under 2 years simple rules only, otherwise it adds the learning model and compares it with the simple rule.

## Run the app
```bash
pip install -e ".[api,dev]"
python -m uvicorn hindsight.app.api:app --port 8100
cd web && npm install && npm run dev      # then open http://localhost:5174
```
The app opens on the bundled sample (the 10 Walmart stores in `data/sample/`, real M5 data). The first run replays five years and takes about a minute; the result is cached and later visits open at once. Load your own file on the Data page. The interface is in English and Arabic (right-to-left); the button at the top right switches.

## Public demo
A recorded-playback build of the sample needs no server: scripts/export_snapshot.py records what the real code answers for the sample into web/public/snapshot/, and VITE_SNAPSHOT=1 npm run build serves those recordings. .github/workflows/pages.yml builds and publishes it to GitHub Pages once the repository is pushed (not done yet).

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

## Licence
Code: MIT (see LICENSE). The bundled sample in data/sample is derived from the M5 Forecasting competition data (Walmart), CC BY 4.0.
