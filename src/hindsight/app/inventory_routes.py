"""Routes for the Decision Optimizer. Kept in their own module (the first of the per-feature routers); `api.create_app` mounts it."""
from typing import Callable

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import Field

from hindsight.app import inventory_service as inv
from hindsight.app import scenario_service
from hindsight.app.service import AUTO, Analysis
from hindsight.inventory.inputs import InventoryInputError, InventorySettings, StockLevel
from hindsight.scenarios.apply import Scenario


class InventoryRequest(InventorySettings):
    method: str = AUTO
    stock: dict[str, StockLevel] = {}


class ScenarioRequest(InventoryRequest):
    scenarios: list[Scenario] = Field(default_factory=list, max_length=8)


def build_router(analyzed: Callable[[str], Analysis]) -> APIRouter:
    router = APIRouter(prefix="/api")

    @router.post("/datasets/{dataset_id}/inventory")
    def inventory(dataset_id: str, body: InventoryRequest):
        a = analyzed(dataset_id)
        try:
            return inv.recommend(a, InventorySettings(**body.model_dump(exclude={"method", "stock"})), body.stock, body.method)
        except InventoryInputError as err:
            return JSONResponse(status_code=422, content={"message": str(err), "code": err.code, "params": err.params})
        except (KeyError, ValueError) as err:
            raise HTTPException(422, str(err.args[0] if err.args else err)) from err

    @router.post("/datasets/{dataset_id}/scenarios")
    def scenarios(dataset_id: str, body: ScenarioRequest):
        """Stateless: the baseline inputs and the scenarios arrive together, nothing is stored, so scenarios cannot leak into each other."""
        a = analyzed(dataset_id)
        try:
            return scenario_service.run(a, InventorySettings(**body.model_dump(exclude={"method", "stock", "scenarios"})), body.stock, body.method, body.scenarios)
        except InventoryInputError as err:
            return JSONResponse(status_code=422, content={"message": str(err), "code": err.code, "params": err.params})
        except (KeyError, ValueError) as err:
            raise HTTPException(422, str(err.args[0] if err.args else err)) from err

    return router
