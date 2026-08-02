"""Price buyback lines against Jita-region market history."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from django.db.models import OuterRef, Subquery
from eveonline.models import EveLocation
from eveuniverse.models import EveMarketPrice, EveType
from industry.helpers.compressed_ore import (
    ORE_BATCH_SIZE,
    ore_materials_per_portion,
)
from market.helpers.pricing import JITA_REGION_ID
from market.models import EveMarketItemHistory

from buyback.helpers.classify import BuybackCategory
from buyback.models import DEFAULT_RATE_RULES


def _baseline_region_id() -> int:
    baseline = EveLocation.objects.filter(price_baseline=True).first()
    if baseline and baseline.region_id:
        return int(baseline.region_id)
    return JITA_REGION_ID


def _history_prices_by_type_id(type_ids: list[int]) -> dict[int, Decimal]:
    """Latest region history average, then EveMarketPrice average."""
    if not type_ids:
        return {}

    unique_ids = list({int(tid) for tid in type_ids})
    region_id = _baseline_region_id()
    prices: dict[int, Decimal] = {}

    latest_date = (
        EveMarketItemHistory.objects.filter(
            region_id=region_id,
            item_id=OuterRef("item_id"),
        )
        .order_by("-date")
        .values("date")[:1]
    )
    for type_id, average in EveMarketItemHistory.objects.filter(
        region_id=region_id,
        item_id__in=unique_ids,
        date=Subquery(latest_date),
    ).values_list("item_id", "average"):
        if average is not None:
            prices[int(type_id)] = Decimal(str(average))

    missing = [tid for tid in unique_ids if tid not in prices]
    if missing:
        for type_id, average in EveMarketPrice.objects.filter(
            eve_type_id__in=missing
        ).values_list("eve_type_id", "average_price"):
            if average is not None:
                prices[int(type_id)] = Decimal(str(average))

    return prices


def get_baseline_buy_prices(
    type_ids: list[int] | None = None,
) -> dict[int, Decimal]:
    """
    Jita guide price per EveType from price_baseline region history.

    Uses EveMarketItemHistory (The Forge when Jita is baseline), with
    EveMarketPrice as a last resort — not live station order-book rows.
    """
    if not type_ids:
        return {}
    return _history_prices_by_type_id(type_ids)


def get_baseline_buy_prices_by_name(
    names: list[str] | None = None,
) -> dict[str, Decimal]:
    """Jita guide prices by item name; same source as get_baseline_buy_prices."""
    if not names:
        return {}
    name_to_id = dict(
        EveType.objects.filter(name__in=names).values_list("name", "id")
    )
    by_id = _history_prices_by_type_id(list(name_to_id.values()))
    return {
        name: by_id[type_id]
        for name, type_id in name_to_id.items()
        if type_id in by_id
    }


def merge_rate_rules(raw) -> dict[str, float]:
    rules = dict(DEFAULT_RATE_RULES)
    if isinstance(raw, dict):
        for key in (
            "ore_refine",
            "ore_jita_buy",
            "p1_jita_buy_cap",
            "other_jita_buy",
        ):
            if key in raw and raw[key] is not None:
                try:
                    rules[key] = float(raw[key])
                except (TypeError, ValueError):
                    pass
    return rules


@dataclass
class PricedLine:
    type_id: Optional[int]
    name: str
    quantity: int
    category: str
    rate: Optional[float]
    unit_price: Optional[float]
    line_total: Optional[float]
    accepted: bool
    reject_reason: Optional[str] = None
    refine_outputs: Optional[dict[str, int]] = None
    jita_buy: Optional[float] = None


def _prorated_refine_outputs(
    name: str,
    quantity: int,
    refine_rate: float,
) -> dict[str, float] | None:
    """
    Mineral outputs for buyback pricing, prorating partial portions.

    In-game refine floors to whole 100-unit batches, but buyback aggregates
    stacks across contracts, so fractional amounts under (and remainders
    above) ORE_BATCH_SIZE are priced in.
    """
    if quantity <= 0 or refine_rate <= 0:
        return None
    per_portion = ore_materials_per_portion(name)
    if not per_portion:
        return None
    fraction = quantity / ORE_BATCH_SIZE
    return {
        mineral: fraction * base_qty * refine_rate
        for mineral, base_qty in per_portion.items()
        if base_qty > 0
    }


def price_ore_line(
    *,
    name: str,
    quantity: int,
    type_id: int | None,
    refine_rate: float,
    ore_jita_buy: float,
    mineral_buy_by_name: dict[str, Decimal],
) -> PricedLine:
    outputs = _prorated_refine_outputs(name, quantity, refine_rate)
    if not outputs:
        if quantity <= 0:
            reject_reason = "Quantity must be positive"
        else:
            reject_reason = "Could not refine ore (no material data)"
        return PricedLine(
            type_id=type_id,
            name=name,
            quantity=quantity,
            category=BuybackCategory.ORE.value,
            rate=None,
            unit_price=None,
            line_total=None,
            accepted=False,
            reject_reason=reject_reason,
        )

    missing = [m for m in outputs if m not in mineral_buy_by_name]
    if missing:
        return PricedLine(
            type_id=type_id,
            name=name,
            quantity=quantity,
            category=BuybackCategory.ORE.value,
            rate=None,
            unit_price=None,
            line_total=None,
            accepted=False,
            reject_reason=f"Missing Jita buy for minerals: {', '.join(missing)}",
            refine_outputs={
                m: int(round(q)) for m, q in outputs.items() if round(q) > 0
            },
        )

    mineral_isk = sum(
        float(mineral_buy_by_name[m]) * qty for m, qty in outputs.items()
    )
    line_total = mineral_isk * ore_jita_buy
    unit_price = line_total / quantity if quantity else 0.0
    return PricedLine(
        type_id=type_id,
        name=name,
        quantity=quantity,
        category=BuybackCategory.ORE.value,
        rate=ore_jita_buy,
        unit_price=round(unit_price, 2),
        line_total=round(line_total, 2),
        accepted=True,
        refine_outputs={
            m: int(round(q)) for m, q in outputs.items() if round(q) > 0
        },
        jita_buy=None,
    )


def price_flat_line(
    *,
    name: str,
    quantity: int,
    type_id: int | None,
    category: BuybackCategory,
    rate: float,
    buy_price: Decimal | None,
) -> PricedLine:
    if buy_price is None:
        return PricedLine(
            type_id=type_id,
            name=name,
            quantity=quantity,
            category=category.value,
            rate=None,
            unit_price=None,
            line_total=None,
            accepted=False,
            reject_reason="Missing Jita buy price",
        )
    jita_buy = float(buy_price)
    unit = jita_buy * rate
    line_total = unit * quantity
    return PricedLine(
        type_id=type_id,
        name=name,
        quantity=quantity,
        category=category.value,
        rate=rate,
        unit_price=round(unit, 2),
        line_total=round(line_total, 2),
        accepted=True,
        jita_buy=round(jita_buy, 2),
    )
