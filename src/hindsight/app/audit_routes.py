"""Routes for the Decision Audit. Everything here is owner-only: the log holds stock levels, costs and decisions."""
from typing import Callable, Literal

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from hindsight.app import audit_service
from hindsight.app.inventory_routes import InventoryRequest
from hindsight.app.service import Analysis
from hindsight.audit.store import AuditError, AuditLog
from hindsight.inventory.inputs import InventoryInputError, InventorySettings
from hindsight.scenarios.apply import Scenario


class DecisionRequest(InventoryRequest):
    strategy: Literal["conservative", "balanced", "high_availability"] = "balanced"
    orders: dict[str, float] = Field(default_factory=dict)  # items the person ordered differently from the recommendation
    note: str = ""
    scenario: Scenario | None = None  # record the decision as planned for this what-if


class OutcomeRequest(BaseModel):
    decision_id: int


def build_router(entry: Callable, analyzed: Callable[[str], Analysis], log: AuditLog, require_owner: Callable[[Request], None]) -> APIRouter:
    router = APIRouter(prefix="/api")

    def guarded(fn):
        try:
            return fn()
        except (AuditError, InventoryInputError) as err:
            return JSONResponse(status_code=422, content={"message": str(err), "code": err.code, "params": err.params})
        except (KeyError, ValueError) as err:
            raise HTTPException(422, str(err.args[0] if err.args else err)) from err

    @router.post("/datasets/{dataset_id}/audit/decisions")
    def record(dataset_id: str, body: DecisionRequest, request: Request):
        require_owner(request)
        a, e = analyzed(dataset_id), entry(dataset_id)
        settings = InventorySettings(**body.model_dump(exclude={"method", "stock", "strategy", "orders", "note", "scenario"}))
        return guarded(lambda: audit_service.record_decision(log, a, e.filename, settings, body.stock, body.method, body.strategy, body.orders, body.note, body.scenario))

    @router.get("/audit/events")
    def events(request: Request):
        require_owner(request)
        decisions = log.events("decision")
        return {"decisions": [{**d, "outcome": log.outcome_of(d["id"])} for d in decisions], "verify": log.verify()}

    @router.get("/audit/verify")
    def verify(request: Request):
        require_owner(request)
        return log.verify()

    @router.get("/audit/export")
    def export(request: Request):
        require_owner(request)
        everything = list(reversed(log.events(limit=1_000_000)))
        return JSONResponse({"verify": log.verify(), "events": everything}, headers={"Content-Disposition": 'attachment; filename="hindsight-audit-log.json"'})

    @router.post("/datasets/{dataset_id}/audit/review")
    def review(dataset_id: str, request: Request):
        require_owner(request)
        return {"decisions": audit_service.review(log, entry(dataset_id).data)}

    @router.post("/datasets/{dataset_id}/audit/outcomes")
    def outcome(dataset_id: str, body: OutcomeRequest, request: Request):
        require_owner(request)
        e = entry(dataset_id)
        return guarded(lambda: audit_service.record_outcome(log, e.data, e.filename, body.decision_id))

    return router
