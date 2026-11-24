"""Routes for the Forecast Health Monitor. Read-only: nothing here changes what the app forecasts."""
from typing import Callable

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from hindsight.app import health_service
from hindsight.app.service import AUTO, Analysis
from hindsight.monitoring.rules import Thresholds


class HealthRequest(BaseModel):
    method: str = AUTO
    thresholds: dict[str, float] = Field(default_factory=dict)  # any of the Thresholds fields; the rest keep their defaults


def build_router(analyzed: Callable[[str], Analysis]) -> APIRouter:
    router = APIRouter(prefix="/api")

    @router.post("/datasets/{dataset_id}/health")
    def health(dataset_id: str, body: HealthRequest):
        a = analyzed(dataset_id)
        unknown = set(body.thresholds) - set(Thresholds.__dataclass_fields__)
        if unknown:
            raise HTTPException(422, f"Unknown threshold: {', '.join(sorted(unknown))}")
        try:
            base = Thresholds()
            T = Thresholds(**{k: type(getattr(base, k))(v) for k, v in body.thresholds.items()})
            return health_service.health(a, body.method, T)
        except (KeyError, ValueError) as err:
            raise HTTPException(422, str(err.args[0] if err.args else err)) from err

    @router.post("/datasets/{dataset_id}/health/challenger")
    def challenger(dataset_id: str, body: HealthRequest):
        a = analyzed(dataset_id)
        try:
            return health_service.challenger(a, body.method)
        except health_service.HealthInputError as err:
            return JSONResponse(status_code=422, content={"message": str(err), "code": err.code, "params": err.params})
        except (KeyError, ValueError) as err:
            raise HTTPException(422, str(err.args[0] if err.args else err)) from err

    return router
