"""What-if scenarios as pure functions: a scenario and the baseline inputs go in, changed copies of those inputs and a demand factor come out.

Nothing here touches the forecast, the stored data or the baseline objects (`apply` never mutates its arguments, which the tests check).
A scenario is a hypothesis the user states. Hindsight does not know whether a promotion will lift sales by 30% or what a price change will do
to demand; it only works out what the stated assumption would mean for orders, stock and cost. Every effect is therefore reported back as an
assumption, and results built on them are never presented as forecasts."""
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from hindsight.inventory.inputs import MAX_WINDOW_DAYS, InventoryInputError, InventorySettings, StockLevel, resolve


class Scenario(BaseModel):
    """Changes to apply to the baseline. Percentages are in percent (20 means +20%). Anything left empty is not applied."""

    name: str = Field("Scenario", min_length=1, max_length=60)
    demand_change_pct: float | None = Field(None, gt=-100, le=500)  # demand over the whole cover period
    promo_uplift_pct: float | None = Field(None, gt=-100, le=500)  # extra demand on the promotion days
    promo_days: int | None = Field(None, ge=1, le=MAX_WINDOW_DAYS)
    seasonal_change_pct: float | None = Field(None, gt=-100, le=500)  # demand change on the days a seasonal pattern applies
    seasonal_days: int | None = Field(None, ge=1, le=MAX_WINDOW_DAYS)
    spike_pct: float | None = Field(None, gt=-100, le=500)  # a short burst of extra demand
    spike_days: int | None = Field(None, ge=1, le=MAX_WINDOW_DAYS)
    supplier_delay_days: int | None = Field(None, ge=1, le=MAX_WINDOW_DAYS)  # deliveries arrive this many days later than the lead time
    stock_reduction_pct: float | None = Field(None, ge=0, le=100)  # stock on hand is lower than recorded (loss, damage, count error)
    price_change_pct: float | None = Field(None, gt=-100, le=500)
    price_elasticity: float | None = None  # what share of demand a 1% price rise removes; the user must supply it, never inferred


@dataclass
class Effect:
    kind: str
    params: dict
    factor: float | None = None  # multiplier on demand, when the effect acts on demand


@dataclass
class Applied:
    settings: InventorySettings
    stock: dict[str, StockLevel]
    demand_factor: float
    window_days: int
    effects: list[Effect] = field(default_factory=list)


def _share_effect(kind: str, pct: float | None, days: int | None, window: int) -> Effect | None:
    """An uplift that applies on `days` of the `window` cover days. Daily demand is taken as flat across the window, so the whole-period
    factor is 1 + uplift * (days / window). A burst longer than the window is cut to the window and reported as such."""
    if pct is None:
        return None
    if days is None:
        raise InventoryInputError(f"For this effect, say how many days it lasts.", "days_missing", effect=kind)
    used = min(days, window)
    return Effect(kind, {"pct": pct, "days": days, "days_applied": used, "window_days": window}, 1 + pct / 100 * used / window)


def apply(s: Scenario, settings: InventorySettings, stock: dict[str, StockLevel]) -> Applied:
    """The inputs as they would be under the scenario, plus the demand factor. Raises `InventoryInputError` (with a code) when the scenario
    cannot be applied honestly. The baseline arguments are left untouched."""
    new_settings = settings.model_copy(deep=True)
    new_stock = {k: v.model_copy(deep=True) for k, v in stock.items()}
    effects: list[Effect] = []

    if s.supplier_delay_days is not None:
        if settings.mode != "periodic_review":
            raise InventoryInputError("A supplier delay changes the lead time, which only exists in regular-ordering mode.", "delay_not_applicable")
        if settings.lead_time_days is None:
            raise InventoryInputError("The supplier lead time is needed to apply a delay to it.", "lead_time_missing")
        new_settings.lead_time_days = settings.lead_time_days + s.supplier_delay_days
        effects.append(Effect("supplier_delay", {"days": s.supplier_delay_days, "lead_time_days": new_settings.lead_time_days}))

    if s.stock_reduction_pct is not None:
        if not any(v.on_hand is not None for v in new_stock.values()):
            raise InventoryInputError("Enter stock on hand for at least one item to apply a stock reduction to it.", "stock_missing")
        for v in new_stock.values():
            if v.on_hand is not None:
                v.on_hand = v.on_hand * (1 - s.stock_reduction_pct / 100)
        effects.append(Effect("stock_reduction", {"pct": s.stock_reduction_pct}))

    if s.price_change_pct is not None:
        if settings.price is None:
            raise InventoryInputError("A price change needs the current selling price.", "price_missing")
        if s.price_elasticity is None:
            raise InventoryInputError("A price change needs a price elasticity from you: how much demand falls when the price rises. Hindsight cannot work it out from sales alone.", "elasticity_missing")
        if s.price_elasticity > 0:
            raise InventoryInputError("A price elasticity above zero would mean demand rises when the price rises. Enter a negative number such as -1.5.", "elasticity_sign")
        new_settings.price = settings.price * (1 + s.price_change_pct / 100)
        effects.append(Effect("price_change", {"pct": s.price_change_pct, "elasticity": s.price_elasticity, "price": new_settings.price},
                              (1 + s.price_change_pct / 100) ** s.price_elasticity))
    elif s.price_elasticity is not None:
        raise InventoryInputError("An elasticity does nothing without a price change. Enter the price change too, or clear the elasticity.", "elasticity_unused")

    window = resolve(new_settings).window_days  # cover period under the changed lead time; also refuses a window beyond the forecast
    if s.demand_change_pct is not None:
        effects.append(Effect("demand_change", {"pct": s.demand_change_pct}, 1 + s.demand_change_pct / 100))
    for kind, pct, days in (("promotion", s.promo_uplift_pct, s.promo_days), ("seasonal", s.seasonal_change_pct, s.seasonal_days), ("spike", s.spike_pct, s.spike_days)):
        e = _share_effect(kind, pct, days, window)
        if e:
            effects.append(e)
        elif days is not None:
            raise InventoryInputError("Enter the size of the effect as well as its number of days.", "pct_missing", effect=kind)

    factor = 1.0
    for e in effects:
        if e.factor is not None:
            factor *= e.factor  # effects are combined by multiplying, so two +10% effects make +21%, not +20%
    return Applied(new_settings, new_stock, factor, window, effects)
