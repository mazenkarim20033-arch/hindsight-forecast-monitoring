"""What a business tells Hindsight about its stock and costs, and what the optimizer may assume when something is missing.

Nothing financial is invented here. Every number the optimizer uses is either given by the user or is one of the few documented defaults
below, and each default used is reported back as an `Assumption` so the screen can show it."""
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field

# Documented defaults. Each one that is used appears in the response as an assumption with source "default".
DEFAULT_REVIEW_DAYS = 7  # how often the business places orders, when the user does not say
DEFAULT_SERVICE_LEVEL = 0.95  # target for the high-availability strategy
DEFAULT_CONSERVATIVE_FACTOR = 0.5  # the conservative strategy counts a lost sale as half as costly as the balanced one does
FALLBACK_LEVELS = {"conservative": 0.80, "balanced": 0.90}  # only when costs are missing, so no cost-based answer exists
MAX_WINDOW_DAYS = 28  # the forecaster looks at most 28 days ahead
STRATEGIES = ("conservative", "balanced", "high_availability")


class InventoryInputError(ValueError):
    """The inputs cannot be used. `code` and `params` let the interface say it in the current language."""

    def __init__(self, message: str, code: str, **params):
        super().__init__(message)
        self.code, self.params = code, params


class InventorySettings(BaseModel):
    """Business parameters, shared by every item. Anything left empty is treated as unknown, never as zero."""

    mode: Literal["periodic_review", "single_period"] = "periodic_review"
    lead_time_days: int | None = Field(None, ge=0, le=MAX_WINDOW_DAYS)
    review_days: int | None = Field(None, ge=1, le=MAX_WINDOW_DAYS)
    period_days: int | None = Field(None, ge=1, le=MAX_WINDOW_DAYS)
    price: float | None = Field(None, ge=0)
    unit_cost: float | None = Field(None, ge=0)
    holding_cost_per_day: float | None = Field(None, ge=0)
    stockout_penalty: float | None = Field(None, ge=0)
    salvage_value: float | None = Field(None, ge=0)
    service_level: float | None = Field(None, gt=0.5, lt=1)
    min_order_qty: float | None = Field(None, ge=0)
    order_multiple: float | None = Field(None, gt=0)
    conservative_factor: float = Field(DEFAULT_CONSERVATIVE_FACTOR, gt=0, le=1)


class StockLevel(BaseModel):
    on_hand: float | None = Field(None, ge=0)
    on_order: float | None = Field(None, ge=0)


@dataclass
class Assumption:
    field: str
    value: float | str
    source: str  # "user" or "default"


@dataclass
class Resolved:
    mode: str
    window_days: int
    cu: float | None  # cost of ordering one unit too few
    co: float | None  # cost of ordering one unit too many
    cost_based: bool  # False: only service levels are available, so no money figures are produced
    levels: dict[str, float]  # strategy -> target probability of covering demand
    assumptions: list[Assumption] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)


def resolve(s: InventorySettings) -> Resolved:
    """Turn the user's settings into the numbers the optimizer needs, recording every default it had to use."""
    notes: list[Assumption] = []
    missing: list[str] = []
    if s.salvage_value is not None and s.unit_cost is not None and s.salvage_value > s.unit_cost:
        raise InventoryInputError("The salvage value is higher than the unit cost. Leftover stock cannot be worth more than it cost.", "salvage_above_cost")

    def given(name: str) -> bool:
        v = getattr(s, name)
        if v is not None:
            notes.append(Assumption(name, v, "user"))
        return v is not None

    if s.mode == "periodic_review":
        if s.lead_time_days is None:
            raise InventoryInputError("The supplier lead time is needed to plan how much to order. Enter how many days a delivery takes (0 if it is same-day).", "lead_time_missing")
        given("lead_time_days")
        review = s.review_days if s.review_days is not None else DEFAULT_REVIEW_DAYS
        notes.append(Assumption("review_days", review, "user" if s.review_days is not None else "default"))
        window = s.lead_time_days + review
    else:
        if s.period_days is None:
            raise InventoryInputError("Enter how many days one selling period lasts (for example 3 for fresh bread).", "period_missing")
        given("period_days")
        window = s.period_days
    if window > MAX_WINDOW_DAYS:
        raise InventoryInputError(f"Lead time plus review period is {window} days. The forecaster looks at most {MAX_WINDOW_DAYS} days ahead, so a longer cover cannot be planned from it.", "window_too_long", days=window, max=MAX_WINDOW_DAYS)

    for name in ("price", "unit_cost", "min_order_qty", "order_multiple"):
        if not given(name) and name in ("price", "unit_cost"):
            missing.append(name)
    cu = co = None
    cost_based = False
    margin_ok = s.price is not None and s.unit_cost is not None
    if margin_ok:
        penalty = s.stockout_penalty or 0.0
        notes.append(Assumption("stockout_penalty", penalty, "user" if s.stockout_penalty is not None else "default"))
        cu = s.price - s.unit_cost + penalty
        if cu <= 0:
            raise InventoryInputError("The selling price is not above the unit cost, so a lost sale costs nothing and there is nothing to optimise. Check the prices, or add a stock-out penalty.", "no_margin")
        if s.mode == "periodic_review":
            if s.holding_cost_per_day is None:
                missing.append("holding_cost_per_day")
            else:
                given("holding_cost_per_day")
                co = s.holding_cost_per_day * (window - s.lead_time_days)  # extra stock is carried for one more review cycle
        else:
            salvage = s.salvage_value if s.salvage_value is not None else 0.0
            notes.append(Assumption("salvage_value", salvage, "user" if s.salvage_value is not None else "default"))
            hold = s.holding_cost_per_day or 0.0
            if s.holding_cost_per_day is not None:
                given("holding_cost_per_day")
            co = s.unit_cost - salvage + hold * window
        cost_based = co is not None and co > 0
        if co is not None and co <= 0:
            raise InventoryInputError("Carrying leftover stock costs nothing with these inputs, so ordering without limit looks free. Enter a holding cost or a unit cost.", "no_overage_cost")
    sl = s.service_level if s.service_level is not None else DEFAULT_SERVICE_LEVEL
    notes.append(Assumption("service_level", sl, "user" if s.service_level is not None else "default"))
    if cost_based:
        f = s.conservative_factor
        notes.append(Assumption("conservative_factor", f, "user" if f != DEFAULT_CONSERVATIVE_FACTOR else "default"))
        balanced = cu / (cu + co)
        levels = {"conservative": f * cu / (f * cu + co), "balanced": balanced, "high_availability": max(sl, balanced)}
    else:
        levels = {**FALLBACK_LEVELS, "high_availability": sl}
        for k, v in FALLBACK_LEVELS.items():
            notes.append(Assumption(f"level_{k}", v, "default"))
    return Resolved(s.mode, window, cu, co, cost_based, levels, notes, missing)
