"""Price buyback lines against price_baseline Jita buy orders."""

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
    reprocess_output,
)
from market.helpers.pricing import JITA_REGION_ID
from market.models import EveMarketItemHistory, EveMarketItemLocationPrice

from buyback.helpers.classify import BuybackCategory
from buyback.models import DEFAULT_RATE_RULES


def _baseline_region_id(baseline: EveLocation | None) -> int:
    if baseline and baseline.region_id:
        return int(baseline.region_id)
    return JITA_REGION_ID


def _fallback_buy_prices_by_type_id(
    type_ids: list[int],
    *,
    region_id: int,
) -> dict[int, Decimal]:
    """
    Region market-history average, then EveMarketPrice average.

    Used when the price_baseline location has no station-range buy order
    (common for Jita NPC station, which is prices_active but not market_active).
    """
    if not type_ids:
        return {}

    unique_ids = list({int(tid) for tid in type_ids})
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
    Highest buy order price per EveType at the price_baseline location.

    Falls back to The Forge history / EveMarketPrice when the baseline
    location has no stored station-range buy (e.g. Jita not market-synced).
    """
    baseline = EveLocation.objects.filter(price_baseline=True).first()
    prices: dict[int, Decimal] = {}
    if baseline:
        qs = EveMarketItemLocationPrice.objects.filter(
            location=baseline, buy_price__isnull=False
        )
        if type_ids is not None:
            qs = qs.filter(item_id__in=type_ids)
        prices = {
            item_id: Decimal(str(buy_price))
            for item_id, buy_price in qs.values_list("item_id", "buy_price")
        }

    if type_ids is None:
        return prices

    missing = [tid for tid in type_ids if tid not in prices]
    if missing:
        prices.update(
            _fallback_buy_prices_by_type_id(
                missing, region_id=_baseline_region_id(baseline)
            )
        )
    return prices


def get_baseline_buy_prices_by_name(
    names: list[str] | None = None,
) -> dict[str, Decimal]:
    """Buy prices by item name; same fallback as get_baseline_buy_prices."""
    baseline = EveLocation.objects.filter(price_baseline=True).first()
    prices: dict[str, Decimal] = {}
    if baseline:
        qs = EveMarketItemLocationPrice.objects.filter(
            location=baseline, buy_price__isnull=False
        )
        if names is not None:
            if not names:
                return {}
            qs = qs.filter(item__name__in=names)
        prices = {
            name: Decimal(str(buy))
            for name, buy in qs.values_list("item__name", "buy_price")
        }

    if names is None:
        return prices

    missing_names = [name for name in names if name not in prices]
    if not missing_names:
        return prices

    name_to_id = dict(
        EveType.objects.filter(name__in=missing_names).values_list(
            "name", "id"
        )
    )
    fallback = _fallback_buy_prices_by_type_id(
        list(name_to_id.values()),
        region_id=_baseline_region_id(baseline),
    )
    for name, type_id in name_to_id.items():
        if type_id in fallback:
            prices[name] = fallback[type_id]
    return prices


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


def price_ore_line(
    *,
    name: str,
    quantity: int,
    type_id: int | None,
    refine_rate: float,
    ore_jita_buy: float,
    mineral_buy_by_name: dict[str, Decimal],
) -> PricedLine:
    outputs = reprocess_output(name, quantity, refine_rate=refine_rate)
    if not outputs:
        if 0 < quantity < ORE_BATCH_SIZE:
            reject_reason = (
                f"Ore stacks under {ORE_BATCH_SIZE} units do not refine "
                f"(in-game portion size)"
            )
        elif not ore_materials_per_portion(name):
            reject_reason = "Could not refine ore (no material data)"
        else:
            reject_reason = (
                f"Could not refine ore (need at least {ORE_BATCH_SIZE} units)"
            )
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
            refine_outputs=outputs,
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
        refine_outputs=outputs,
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
