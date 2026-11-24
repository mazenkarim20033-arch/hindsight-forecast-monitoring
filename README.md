# Hindsight: forecasts you can check, and decisions you can review

Hindsight forecasts daily sales for each item or store, shows how that forecast would have performed over the past using only what was known at each date, turns it into order recommendations from your own costs and stock, and keeps a tamper-evident record of each decision so it can be compared with what happened. It runs on your computer, in English and right-to-left Arabic.

**Status.** All seven milestones of the decision-support upgrade are built and tested locally (207 Python and 43 web tests). Publishing the new work (commit, push, redeploy the public demo) waits for the owner's approval. The Arabic wording has not been reviewed by a native speaker. Nothing here has been tested on a real business yet: the evidence is the public M5 Walmart data (US retail) and synthetic files. Start with [docs/PROJECT_OVERVIEW.md](docs/PROJECT_OVERVIEW.md).

## What it does
| Area | In one line |
|---|---|
| **Forecast with a track record** | Next-days forecast per item with a range whose coverage is measured, plain-language reasons, odd-day alerts, a replay lab and a scorecard against a simple rule |
| **Decision Optimizer** | How much to order under three options, from your lead time, costs and stock; every assumption labelled; a measured check of how often each service level held |
| **What-if Scenarios** | Demand change, promotion, supplier delay, lower stock and price change (with your own elasticity) next to the baseline, always labelled hypothetical |
| **Forecast Health Monitor** | Healthy, Watch or Action needed from recent error and range coverage; demand drift shown as information; an optional retrained-model test that is never deployed |
| **Smart Data Onboarding** | Finds columns in English and Arabic, names items from several columns, handles duplicates, reads price/cost/stock columns, flags data-quality problems, remembers how to read a kind of file |
| **Decision Audit** | An append-only, hash-chained record of each decision (what was advised, what was ordered, why) and later the outcome |

The app opens on a bundled sample (10 Walmart stores), never on an upload screen. It chooses methods by how much history there is: under 120 days it asks for more, under two years simple rules only, otherwise it adds the learning model and compares it with the simple rule.

## What the evidence says (public M5 data, US retail)
- The learning model beats the best simple rule by 2 to 3 WAPE points at every aggregated level (all stores 4.5% against 7.5%; one store 7.5% against 9.8%).
- Stated 80% and 90% ranges held on 79 to 84% and 89 to 93% of days.
- A stated 95% order service level held 94.5% (3-day cover) down to 91.5% (28-day cover): slightly under target, and the screen shows that table.
- The health monitor left "healthy" a median of 3 to 4 days after an injected 50% rise or 30% fall on synthetic data; on M5 about a quarter of store-days were not healthy, with no known broken period to compare against.
- **Not evidenced:** anything about Egyptian shops; money figures on a real business (the sample has no prices, costs or stock); price or promotion effects; health thresholds on real shops. See [docs/LIMITATIONS.md](docs/LIMITATIONS.md).

## Run the app
```bash
pip install -e ".[api,dev]"
python -m uvicorn hindsight.app.api:app --port 8100
cd web && npm install && npm run dev      # then open http://localhost:5174
```
The first run on the sample replays five years and takes about a minute; the result is cached and later visits open at once. Load your own file on the **Data** page (CSV or Excel). The button at the top right switches between English and Arabic.

## Where things are
| I want to | Go to |
|---|---|
| Understand the project and what is proven | [docs/PROJECT_OVERVIEW.md](docs/PROJECT_OVERVIEW.md) |
| See how each feature works, its maths, tests and limits | [docs/FEATURE_DOCUMENTATION.md](docs/FEATURE_DOCUMENTATION.md) |
| See how the parts connect | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| Know what each model or rule is, and where not to use it | [docs/MODEL_CARD.md](docs/MODEL_CARD.md) |
| Know every field the app reads or writes | [docs/DATA_DICTIONARY.md](docs/DATA_DICTIONARY.md) |
| See what has and has not been evaluated, and the studies still needed | [docs/EVALUATION_PLAN.md](docs/EVALUATION_PLAN.md) |
| See what does not work yet | [docs/LIMITATIONS.md](docs/LIMITATIONS.md) and [docs/ROADMAP.md](docs/ROADMAP.md) |
| Explain it to someone else | [docs/INTERVIEW_GUIDE.md](docs/INTERVIEW_GUIDE.md) and [docs/CASE_STUDY.md](docs/CASE_STUDY.md) |
| Read the original forecasting results | [docs/EXPERIMENTS.md](docs/EXPERIMENTS.md), [docs/DATASET_CARD.md](docs/DATASET_CARD.md), `reports/` |

## Who can load data
Only the owner. The public demo is static and read-only. On your own computer the server recognises you (same machine, no proxy), so **Load your data** just works. For a server other people can reach, set a secret before starting it and type it once on the Data page:

```bash
HINDSIGHT_OWNER_KEY=choose-a-long-secret python -m uvicorn hindsight.app.api:app --port 8100
```

Without the key nobody else can upload, re-map, analyse a file or read the decision log; everyone can still use the bundled sample. Uploaded files stay in memory and are never written to disk. Apart from the cached analysis of the bundled sample, the only things the app stores are the decision log and saved adapters (`artifacts/audit/`, `artifacts/adapters/`, all git-ignored); set `HINDSIGHT_AUDIT_DB` to keep the log elsewhere.

## Public demo
A recorded-playback build of the sample needs no server: `scripts/export_snapshot.py` records what the real code answers for the sample into `web/public/snapshot/`, and `VITE_SNAPSHOT=1 npm run build` serves those recordings. It includes one recorded optimizer example, five recorded scenarios, the recorded health status and one recorded retrained-model test; it cannot load files or keep a decision log. `.github/workflows/pages.yml` builds and publishes it to GitHub Pages once the repository is pushed.

## Setup and tests
```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -e ".[api,dev]"
python -m pytest -q                                   # 207 tests
cd web && npm install && npx vitest run               # 43 tests
```
To regenerate the research results, download the M5 zip (48 MB, CC BY 4.0) from https://zenodo.org/records/12636070, extract it into `data/raw/extracted/`, then run `python scripts/eda_m5.py`, `run_baselines.py`, `run_models.py`, `run_alerts.py`. The decision-feature checks are `scripts/run_inventory_check.py`, `run_health_check.py` and `run_perf_check.py`; each writes to `reports/`.

## Limits
Results are on US retail data and synthetic files. Nothing is claimed for Egyptian businesses, and no real shop has run it end to end. Sales are not demand (a stock-out hides it). Scenario results are arithmetic on assumptions you type. The decision log is tamper-evident, not tamper-proof. See [docs/LIMITATIONS.md](docs/LIMITATIONS.md).

Data: M5 Forecasting competition data (Walmart), via Zenodo, CC BY 4.0.

## Licence
Code: MIT (see LICENSE). The bundled sample in `data/sample` is derived from the M5 Forecasting competition data (Walmart), CC BY 4.0.
