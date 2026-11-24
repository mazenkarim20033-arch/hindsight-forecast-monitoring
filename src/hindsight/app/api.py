"""The web API. One in-memory workspace per server process: uploaded files, their cleaned data and the latest analysis of each.

Files are kept in memory only and are not written to disk. Restarting the server forgets them."""
import hmac
import os
import threading
import traceback
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from hindsight.app import audit_routes, inventory_routes, monitoring_routes, service
from hindsight.data.importer import ImportProblem, read_sales_file
from hindsight.audit.store import AuditLog
from hindsight.data import adapters, quality
from hindsight.data.sales import SalesData

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
ROOT = Path(__file__).resolve().parents[3]
SAMPLE_DIR = ROOT / "data" / "sample"
WEB_DIST = ROOT / "web" / "dist"
CACHE_DIR = ROOT / "artifacts" / "cache"
ADAPTERS_BUILTIN = ROOT / "adapters"  # shipped examples
ADAPTERS_SAVED = ROOT / "artifacts" / "adapters"  # saved from the confirm screen
OWNER_KEY_ENV = "HINDSIGHT_OWNER_KEY"
AUDIT_DB_ENV = "HINDSIGHT_AUDIT_DB"
LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost", "testclient"}


class OwnerOnly(Exception):
    """Loading your own data is limited to the owner of this installation."""


@dataclass
class Entry:
    id: str
    filename: str
    raw: bytes | None
    data: SalesData
    report: dict
    detection: dict
    analysis: service.Analysis | None = None
    is_sample: bool = False


@dataclass
class Job:
    id: str
    dataset: str
    state: str = "running"  # running, done, failed
    progress: float = 0.0
    message: str = "Starting"
    error: str | None = None


class MappingBody(BaseModel):
    date: str | None = None
    value: str | None = None
    item: str | None = None
    item_columns: list[str] | None = None
    item_cols: list[str] | None = None  # several columns that together name an item
    business: dict[str, str | None] | None = None  # price, unit_cost, on_hand, on_order -> column
    duplicates: str | None = None  # "sum" or "drop_exact"
    adapter: str | None = None  # apply a saved adapter instead of the fields above


class AdapterBody(BaseModel):
    name: str
    description: str = ""
    overwrite: bool = False


class AnalysisBody(BaseModel):
    horizon: int = 28
    calendar: str = "none"


def _adapter_hint(e: Entry) -> dict | None:
    """The adapter that fits this file's columns, and whether the current choices already are its choices."""
    found, _ = adapters.list_adapters(ADAPTERS_BUILTIN, ADAPTERS_SAVED)
    best = adapters.match([a for a, _ in found], [c["name"] for c in e.detection["columns"]])
    if best is None:
        return None
    m = best.mapping
    same = (e.detection["date"] == m.date and (e.detection["item_columns"] == m.item_columns if m.item_columns else
            (e.detection["value"], e.detection["item"], e.detection["item_cols"]) == (m.value, m.item, m.item_cols)))
    return {"name": best.name, "description": best.description, "applied": bool(same)}


def _summary(e: Entry) -> dict:
    d = e.data
    return {"quality": quality.assess(d), "adapter": _adapter_hint(e), "id": e.id, "filename": e.filename, "is_sample": e.is_sample, "report": e.report, "detection": e.detection,
            "n_series": d.n_series, "n_days": d.n_days, "first_date": str(d.dates[0].date()), "last_date": str(d.dates[-1].date()),
            "has_events": "event_name_1" in d.calendar.columns, "analyzed": e.analysis is not None,
            "plan": {"tier": (p := service.plan_for(d.n_days, 28)).tier, "text": p.explanation, "params": p.params}}


def _note_dicts(notes) -> list[dict]:
    return [{"level": n.level, "text": n.text, "code": n.code, "params": n.params} for n in notes]


def _describe(data: SalesData, report, det) -> tuple[dict, dict]:
    rep = asdict(report)
    rep["notes"] = _note_dicts(report.notes)
    d = {"layout": det.layout, "date": det.date_col, "value": det.value_col, "item": det.id_col, "item_columns": det.series_cols, "item_cols": det.id_cols,
         "business": det.business, "duplicates": det.duplicates, "columns": det.columns}
    return rep, d


def load_sample() -> tuple[SalesData, dict, dict]:
    raw = (SAMPLE_DIR / "m5_stores.csv").read_bytes()
    data, report, det = read_sales_file(raw, "m5_stores.csv")
    cal = pd.read_csv(SAMPLE_DIR / "m5_events.csv")
    cal["date"] = pd.to_datetime(cal["date"])
    data.calendar = cal.set_index("date").reindex(data.dates).reset_index().rename(columns={"index": "date"})
    data.source = "M5 (Walmart), CC BY 4.0: 10 US stores"
    rep, d = _describe(data, report, det)
    return data, rep, d


def create_app(serve_web: bool = True, owner_key: str | None = None, audit_db: Path | None = None) -> FastAPI:
    """`owner_key` (or the HINDSIGHT_OWNER_KEY environment variable) turns on key protection: loading data then needs the key in an
    X-Owner-Key header. With no key set, loading data is allowed only from the same computer the server runs on, and never through a proxy."""
    key = owner_key if owner_key is not None else (os.environ.get(OWNER_KEY_ENV) or None)
    app = FastAPI(title="Hindsight", version="0.1.0")
    api = APIRouter(prefix="/api")
    datasets: dict[str, Entry] = {}
    jobs: dict[str, Job] = {}

    @app.exception_handler(ImportProblem)
    async def _import_problem(_, exc: ImportProblem):
        return JSONResponse(status_code=422, content={"message": str(exc), "code": exc.code, "params": exc.params})

    @app.exception_handler(OwnerOnly)
    async def _owner_only(_, exc: OwnerOnly):
        return JSONResponse(status_code=403, content={"message": "Only the owner can load files here.", "code": "owner_only", "params": {}})

    def is_owner(request: Request) -> bool:
        if key:
            return hmac.compare_digest(request.headers.get("x-owner-key", "").encode(), key.encode())
        return (request.client.host if request.client else "") in LOCAL_HOSTS and "x-forwarded-for" not in request.headers

    def require_owner(request: Request) -> None:
        if not is_owner(request):
            raise OwnerOnly()

    def entry(dataset_id: str) -> Entry:
        if dataset_id not in datasets:
            raise HTTPException(404, "That file is no longer loaded. Upload it again.")
        return datasets[dataset_id]

    def analyzed(dataset_id: str) -> service.Analysis:
        e = entry(dataset_id)
        if e.analysis is None:
            raise HTTPException(409, "Run the replay for this file first.")
        return e.analysis

    @api.get("/health")
    def health():
        return {"status": "ok"}

    @api.get("/owner")
    def owner(request: Request):
        return {"required": bool(key), "allowed": is_owner(request)}

    @api.post("/datasets")
    async def upload(request: Request, file: UploadFile = File(...)):
        require_owner(request)
        raw = await file.read(MAX_UPLOAD_BYTES + 1)
        if len(raw) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, f"The file is larger than {MAX_UPLOAD_BYTES // 1024 // 1024} MB. Send fewer columns or a shorter period.")
        data, report, det = read_sales_file(raw, file.filename or "upload.csv")
        rep, d = _describe(data, report, det)
        e = Entry(uuid.uuid4().hex[:12], file.filename or "upload.csv", raw, data, rep, d)
        datasets[e.id] = e
        return _summary(e)

    @api.post("/datasets/sample")
    def sample():
        data, rep, d = load_sample()
        e = Entry(uuid.uuid4().hex[:12], "Sample: 10 Walmart stores (public M5 data)", None, data, rep, d, is_sample=True)
        datasets[e.id] = e
        return _summary(e)

    @api.post("/datasets/{dataset_id}/mapping")
    def remap(dataset_id: str, body: MappingBody, request: Request):
        require_owner(request)
        e = entry(dataset_id)
        if e.raw is None:
            raise HTTPException(400, "The sample file cannot be re-read with other columns.")
        if body.adapter:
            found, _ = adapters.list_adapters(ADAPTERS_BUILTIN, ADAPTERS_SAVED)
            chosen = next((a for a, _ in found if a.name == body.adapter), None)
            if chosen is None:
                raise HTTPException(404, f"There is no adapter named '{body.adapter}'.")
            mapping = adapters.to_mapping(chosen)
        else:
            mapping = {"date": body.date, "value": body.value, "item": body.item, "item_columns": body.item_columns, "item_cols": body.item_cols,
                       "business": body.business, "duplicates": body.duplicates}
        data, report, det = read_sales_file(e.raw, e.filename, {k: v for k, v in mapping.items() if v is not None or k == "item"})
        e.data, (e.report, e.detection), e.analysis = data, _describe(data, report, det), None
        return _summary(e)

    @api.get("/adapters")
    def list_adapters():
        found, bad = adapters.list_adapters(ADAPTERS_BUILTIN, ADAPTERS_SAVED)
        return {"adapters": [{"name": a.name, "description": a.description, "columns": a.columns, "source": src} for a, src in found], "unreadable": bad}

    @api.post("/datasets/{dataset_id}/adapters")
    def save_adapter(dataset_id: str, body: AdapterBody, request: Request):
        require_owner(request)
        e = entry(dataset_id)
        if e.raw is None:
            raise HTTPException(400, "The sample file is described by a built-in adapter; load your own file to save one.")
        try:
            a = adapters.from_import(body.name, body.description, e.report["mapping"], e.detection, e.report["mapping"].get("duplicates", "sum"))
            adapters.save(ADAPTERS_SAVED, a, overwrite=body.overwrite)
        except adapters.AdapterError as err:
            return JSONResponse(status_code=422, content={"message": str(err), "code": err.code, "params": err.params})
        return _summary(e)

    @api.post("/datasets/{dataset_id}/analysis")
    def start(dataset_id: str, body: AnalysisBody, request: Request):
        e = entry(dataset_id)
        if not e.is_sample:
            require_owner(request)
        settings = service.Settings(horizon=body.horizon, calendar=body.calendar)
        try:
            settings.validate(e.data)
            if service.plan_for(e.data.n_days, settings.horizon).tier == "too_little":
                raise ValueError(service.plan_for(e.data.n_days, settings.horizon).explanation)
        except ValueError as err:
            raise HTTPException(422, str(err)) from err
        job = Job(uuid.uuid4().hex[:12], e.id)
        jobs[job.id] = job

        def work():
            def progress(p: float, msg: str):
                job.progress, job.message = float(p), msg
            try:
                e.analysis = service.run_analysis(e.data, settings, progress, CACHE_DIR if e.is_sample else None)  # uploads are never written to disk
                job.state, job.progress, job.message = "done", 1.0, "Done"
            except Exception as err:  # noqa: BLE001 - report any failure to the user instead of hanging the job
                traceback.print_exc()
                job.state, job.error, job.message = "failed", f"{type(err).__name__}: {err}", "Failed"

        threading.Thread(target=work, daemon=True).start()
        return asdict(job)

    @api.get("/jobs/{job_id}")
    def job_status(job_id: str):
        if job_id not in jobs:
            raise HTTPException(404, "Unknown job.")
        return asdict(jobs[job_id])

    @api.get("/datasets/{dataset_id}")
    def info(dataset_id: str):
        return _summary(entry(dataset_id))

    @api.get("/datasets/{dataset_id}/overview")
    def overview(dataset_id: str):
        return service.overview(analyzed(dataset_id))

    @api.get("/datasets/{dataset_id}/scorecard")
    def scorecard(dataset_id: str):
        return service.scorecard(analyzed(dataset_id))

    @api.get("/datasets/{dataset_id}/stage")
    def stage(dataset_id: str, item: str | None = None, method: str = service.AUTO, level: float = 0.8, last_days: int = 420):
        try:
            return service.stage(analyzed(dataset_id), item, method, level, min(max(last_days, 60), 2000))
        except (KeyError, ValueError) as err:
            raise HTTPException(422, str(err.args[0] if err.args else err)) from err

    @api.get("/datasets/{dataset_id}/next")
    def next_forecast(dataset_id: str, item: str | None = None, method: str = service.AUTO, level: float = 0.8, day: int = 0):
        try:
            return service.next_view(analyzed(dataset_id), item, method, level, day)
        except (KeyError, ValueError) as err:
            raise HTTPException(422, str(err.args[0] if err.args else err)) from err

    @api.get("/datasets/{dataset_id}/alerts")
    def odd_days(dataset_id: str, method: str = service.AUTO, item: str | None = None):
        try:
            return service.alerts(analyzed(dataset_id), method, item=item)
        except KeyError as err:
            raise HTTPException(422, "Unknown method.") from err

    @api.get("/datasets/{dataset_id}/planner")
    def planner(dataset_id: str, item: str | None = None, method: str = service.AUTO):
        try:
            return service.stock_plan(analyzed(dataset_id), item, method)
        except (KeyError, ValueError) as err:
            raise HTTPException(422, str(err.args[0] if err.args else err)) from err

    @api.get("/datasets/{dataset_id}/effects")
    def effects(dataset_id: str):
        return service.holiday_effects(entry(dataset_id).data)

    @api.get("/datasets/{dataset_id}/dashboard")
    def dashboard(dataset_id: str, method: str = service.AUTO):
        try:
            return service.dashboard(analyzed(dataset_id), method)
        except KeyError as err:
            raise HTTPException(422, "Unknown method.") from err

    @api.get("/datasets/{dataset_id}/total")
    def total(dataset_id: str, method: str = service.AUTO, level: float = 0.8):
        try:
            return service.total_next(analyzed(dataset_id), method, level)
        except (KeyError, ValueError) as err:
            raise HTTPException(422, str(err.args[0] if err.args else err)) from err

    app.include_router(api)
    app.include_router(inventory_routes.build_router(analyzed))
    app.include_router(monitoring_routes.build_router(analyzed))
    audit_log = AuditLog(audit_db or Path(os.environ.get(AUDIT_DB_ENV) or ROOT / "artifacts" / "audit" / "audit.sqlite"))  # opened on first use
    app.include_router(audit_routes.build_router(entry, analyzed, audit_log, require_owner))
    if serve_web and WEB_DIST.exists():
        app.mount("/", StaticFiles(directory=WEB_DIST, html=True), name="web")
    return app


app = create_app()
