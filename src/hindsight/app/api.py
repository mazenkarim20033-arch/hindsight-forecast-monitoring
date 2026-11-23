"""The web API. One in-memory workspace per server process: uploaded files, their cleaned data and the latest analysis of each.

Files are kept in memory only and are not written to disk. Restarting the server forgets them."""
import threading
import traceback
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from hindsight.app import service
from hindsight.data.importer import ImportProblem, read_sales_file
from hindsight.data.sales import SalesData

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
ROOT = Path(__file__).resolve().parents[3]
SAMPLE_DIR = ROOT / "data" / "sample"
WEB_DIST = ROOT / "web" / "dist"
CACHE_DIR = ROOT / "artifacts" / "cache"


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


class AnalysisBody(BaseModel):
    horizon: int = 28
    calendar: str = "none"


def _summary(e: Entry) -> dict:
    d = e.data
    return {"id": e.id, "filename": e.filename, "is_sample": e.is_sample, "report": e.report, "detection": e.detection,
            "n_series": d.n_series, "n_days": d.n_days, "first_date": str(d.dates[0].date()), "last_date": str(d.dates[-1].date()),
            "has_events": "event_name_1" in d.calendar.columns, "analyzed": e.analysis is not None,
            "plan": {"tier": (p := service.plan_for(d.n_days, 28)).tier, "text": p.explanation, "params": p.params}}


def _note_dicts(notes) -> list[dict]:
    return [{"level": n.level, "text": n.text, "code": n.code, "params": n.params} for n in notes]


def _describe(data: SalesData, report, det) -> tuple[dict, dict]:
    rep = asdict(report)
    rep["notes"] = _note_dicts(report.notes)
    d = {"layout": det.layout, "date": det.date_col, "value": det.value_col, "item": det.id_col, "item_columns": det.series_cols, "columns": det.columns}
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


def create_app(serve_web: bool = True) -> FastAPI:
    app = FastAPI(title="Hindsight", version="0.1.0")
    api = APIRouter(prefix="/api")
    datasets: dict[str, Entry] = {}
    jobs: dict[str, Job] = {}

    @app.exception_handler(ImportProblem)
    async def _import_problem(_, exc: ImportProblem):
        return JSONResponse(status_code=422, content={"message": str(exc), "code": exc.code, "params": exc.params})

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

    @api.post("/datasets")
    async def upload(file: UploadFile = File(...)):
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
    def remap(dataset_id: str, body: MappingBody):
        e = entry(dataset_id)
        if e.raw is None:
            raise HTTPException(400, "The sample file cannot be re-read with other columns.")
        mapping = {"date": body.date, "value": body.value, "item": body.item, "item_columns": body.item_columns}
        data, report, det = read_sales_file(e.raw, e.filename, {k: v for k, v in mapping.items() if v is not None or k == "item"})
        e.data, (e.report, e.detection), e.analysis = data, _describe(data, report, det), None
        return _summary(e)

    @api.post("/datasets/{dataset_id}/analysis")
    def start(dataset_id: str, body: AnalysisBody):
        e = entry(dataset_id)
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
    def odd_days(dataset_id: str, method: str = service.AUTO):
        try:
            return service.alerts(analyzed(dataset_id), method)
        except KeyError as err:
            raise HTTPException(422, "Unknown method.") from err

    app.include_router(api)
    if serve_web and WEB_DIST.exists():
        app.mount("/", StaticFiles(directory=WEB_DIST, html=True), name="web")
    return app


app = create_app()
