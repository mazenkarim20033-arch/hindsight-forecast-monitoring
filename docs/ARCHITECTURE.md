# Architecture

## Implemented today
```
data/        importer.py (CSV/Excel -> SalesData, composite keys, duplicate rule, price/cost/stock columns), sales.py (the data contract),
             quality.py (findings on cleaned data), adapters.py (saved YAML column mappings), m5.py (loader)
adapters/    shipped example adapters (saved ones go to artifacts/adapters/)
replay/      engine (rolling origin, no future), baselines, ml (global LightGBM), intervals (conformal), select,
             metrics, scorecard, explain (TreeSHAP), alerts
inventory/   inputs.py (settings, defaults, refusals), newsvendor.py (pure arithmetic: quantile, order rules, outcomes, money)
audit/       store.py (append-only, hash-chained SQLite log), outcome.py (what happened, pure arithmetic)
monitoring/  drift.py (PSI, KS), rules.py (thresholds, status grading): pure
scenarios/   apply.py (what-if effects as pure functions on copies of the inputs)
app/         service.py (replay views), inventory_service.py (forecast + arithmetic), scenario_service.py (baseline vs scenarios), health_service.py (status as of a day, challenger), audit_service.py (record decisions, check outcomes),
             api.py, inventory_routes.py (optimizer, scenarios), monitoring_routes.py (health), audit_routes.py (decision log)
web/src/     pages, components, i18n (EN/AR), api client with a recorded-playback mode for the public demo
```
Layers depend downward only: `inventory/` knows nothing about forecasting or files; `inventory_service` is the only place the two meet. New features are added as their own package plus their own router, mounted by `api.create_app`. The older routes still live in `api.py`; moving them into routers is deferred rather than done as a risky rewrite.

## How the pieces connect
File -> onboarding -> cleaned daily sales -> replay and forecast. The forecast feeds the optimizer (and, through it, scenarios and the decision log) and the health monitor. Health is shown on the dashboard and above the order advice; the decision log stores the health of the moment. An outcome is worked out from a later version of the same file, accepted only if its history up to the decision day has the recorded fingerprint. The browser never supplies numbers the server then trusts: the server recomputes recommendations, scenarios and decisions.

Menu: Dashboard, Items, Orders, Reliability, Decision log, Data, and More (holiday effects, replay lab, scorecard).

## Planned (not built)
The final presentation (Milestone 7).
