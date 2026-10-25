"""
Order line pricing: Jita buy / split / sell or a margin over build cost.

The floor is the Amamake build cost per unit for the line's whole batch
(the same plan the order profit breakdown uses), so a bigger batch can
open a cheaper preset. "Jita delivered" is Jita sell plus the inbound
freight to ship the finished items in, which is what the orderer saves
against.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from typing import Optional, Tuple

from django.core.cache import cache
from eveuniverse.models import EveType

from industry.helpers.freight_costs import estimate_freight_cost
from industry.helpers.product_unit_cost import (
    FACILITY_KEY,
    plan_product_unit_cost,
)
from market.helpers.pricing import baseline_book

logger = logging.getLogger(__name__)

PRICE_BASES = ("jita_buy", "jita_split", "jita_sell", "margin")
PRESET_FIELDS = {
    "jita_buy": "jita_buy",
    "jita_split": "jita_split",
    "jita_sell": "jita_sell",
}
CACHE_SECONDS = 15 * 60


@dataclass(frozen=True)
class LinePricing:
    type_id: int
    quantity: int
    build_cost_per_unit: int
    jita_buy: Optional[int]
    jita_split: Optional[int]
    jita_sell: Optional[int]
    ship_in_per_unit: int
    jita_delivered: Optional[int]


def _whole(value) -> Optional[int]:
    if value is None:
        return None
    whole = int(value)
    return whole if whole > 0 else None


def _ship_in_per_unit(type_id: int, quantity: int, jita_sell: Optional[int]):
    eve_type = EveType.objects.filter(id=type_id).first()
    if eve_type is None:
        return 0
    volume = float(
        getattr(eve_type, "packaged_volume", None) or eve_type.volume or 0
    )
    if volume <= 0:
        return 0
    estimate = estimate_freight_cost(
        facility_key=FACILITY_KEY,
        volume_m3=volume * quantity,
        collateral_isk=(jita_sell or 0) * quantity,
    )
    return int(round(estimate.freight_isk / quantity))


def _compute_line_pricing(type_id: int, quantity: int) -> LinePricing:
    book = baseline_book([type_id]).get(type_id)
    jita_buy = _whole(book.buy) if book else None
    jita_split = _whole(book.split) if book else None
    jita_sell = _whole(book.sell) if book else None
    unit = plan_product_unit_cost(type_id, quantity=quantity)
    if jita_sell is None:
        jita_sell = _whole(unit.jita_sell)
    ship_in = _ship_in_per_unit(type_id, quantity, jita_sell)
    return LinePricing(
        type_id=type_id,
        quantity=quantity,
        build_cost_per_unit=int(unit.cost_per),
        jita_buy=jita_buy,
        jita_split=jita_split,
        jita_sell=jita_sell,
        ship_in_per_unit=ship_in,
        jita_delivered=jita_sell + ship_in if jita_sell else None,
    )


def line_pricing(type_id: int, quantity: int) -> LinePricing:
    """Build-cost floor and Jita prices for one line, cached per batch size."""
    type_id = int(type_id)
    quantity = max(int(quantity), 1)
    key = f"industry:order_line_pricing:{type_id}:{quantity}"
    cached = cache.get(key)
    if cached:
        return LinePricing(**cached)
    pricing = _compute_line_pricing(type_id, quantity)
    cache.set(key, asdict(pricing), CACHE_SECONDS)
    return pricing


def resolve_unit_price(
    pricing: LinePricing,
    basis: str,
    margin_percent: Optional[float] = None,
) -> Tuple[int, str, float]:
    """
    Unit price for a basis, never below the build cost.

    Returns (price, basis actually used, margin percent over build cost).
    A preset with no market price or one under the floor falls back to
    the floor (a 0% margin).
    """
    floor = pricing.build_cost_per_unit
    if basis in PRESET_FIELDS:
        preset = getattr(pricing, PRESET_FIELDS[basis])
        if preset is not None and preset >= floor:
            return preset, basis, _margin_of(preset, floor)
        return floor, "margin", 0.0
    margin = max(float(margin_percent or 0), 0.0)
    return int(round(floor * (1 + margin / 100))), "margin", margin


def _margin_of(price: int, floor: int) -> float:
    if floor <= 0:
        return 0.0
    return round((price - floor) / floor * 100, 1)
