"""Price buyback lines against live Jita buy, with history fallback."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from eveonline.models import EveLocation
from eveuniverse.models import EveType
from industry.helpers.compressed_ore import (
    ORE_BATCH_SIZE,
    ore_materials_per_portion,
)
from market.helpers.pricing import get_history_averages_by_type_id
from market.models import EveMarketItemLocationPrice

from buyback.helpers.classify import BuybackCategory
from buyback.models import DEFAULT_RATE_RULES


def _history_prices_by_type_id(type_ids: list[int]) -> dict[int, Decimal]:
    """Latest region history average, then EveMarketPrice average."""
    if not type_ids:
        return {}
    return get_history_averages_by_type_id(type_ids)


def _live_jita_buys_by_type_id(type_ids: list[int]) -> dict[int, Decimal]:
    """Station-range Jita buy, then split, at the price_baseline location."""
    if not type_ids:
        return {}
    unique_ids = list({int(tid) for tid in type_ids})
    baseline = EveLocation.objects.filter(price_baseline=True).first()
    if baseline is None:
        return {}
    prices: dict[int, Decimal] = {}
    rows = EveMarketItemLocationPrice.objects.filter(
        location=baseline,
        item_id__in=unique_ids,
    ).values_list("item_id", "buy_price", "split_price")
    for type_id, buy_price, split_price in rows:
        if buy_price is not None:
            prices[int(type_id)] = Decimal(str(buy_price))
        elif split_price is not None:
            prices[int(type_id)] = Decimal(str(split_price))
    return prices


def get_baseline_buy_prices(
    type_ids: list[int] | None = None,
) -> dict[int, Decimal]:
    """
    Jita buy per EveType at the price_baseline location.

    Prefers EveMarketItemLocationPrice.buy_price, then split_price.
    Types with no live buy/split fall back to Forge history average
    (then EveMarketPrice) so missing station-range buys do not reject.
    """
    if not type_ids:
        return {}
    unique_ids = list({int(tid) for tid in type_ids})
    prices = _live_jita_buys_by_type_id(unique_ids)
    missing = [tid for tid in unique_ids if tid not in prices]
    if missing:
        prices.update(_history_prices_by_type_id(missing))
    return prices


def get_baseline_buy_prices_by_name(
    names: list[str] | None = None,
) -> dict[str, Decimal]:
    """Jita buy by item name; same source as get_baseline_buy_prices."""
    if not names:
        return {}
    name_to_id = dict(
        EveType.objects.filter(name__in=names).values_list("name", "id")
    )
    by_id = get_baseline_buy_prices(list(name_to_id.values()))
    return {
        name: by_id[type_id]
        for name, type_id in name_to_id.items()
        if type_id in by_id
    }


_PUBLIC_RATE_KEYS = ("ore_refine", "demand_jita_buy", "surplus_jita_buy")


def merge_rate_rules(raw) -> dict[str, float]:
    """
    Merge stored rate_rules into the live public keys.

    Legacy admin JSON may still have other_jita_buy / p1_jita_buy_cap; those
    map to demand / surplus only when the new keys are absent.
    """
    rules = dict(DEFAULT_RATE_RULES)
    if not isinstance(raw, dict):
        return rules

    for key in _PUBLIC_RATE_KEYS:
        if key in raw and raw[key] is not None:
            try:
                rules[key] = float(raw[key])
            except (TypeError, ValueError):
                pass

    if "demand_jita_buy" not in raw and "other_jita_buy" in raw:
        try:
            rules["demand_jita_buy"] = float(raw["other_jita_buy"])
        except (TypeError, ValueError):
            pass
    if "surplus_jita_buy" not in raw and "p1_jita_buy_cap" in raw:
        try:
            rules["surplus_jita_buy"] = float(raw["p1_jita_buy_cap"])
        except (TypeError, ValueError):
            pass
    return {key: rules[key] for key in _PUBLIC_RATE_KEYS}


def public_rate_rules(raw=None) -> dict[str, float]:
    """Live rate knobs for API responses (never exposes legacy keys)."""
    return merge_rate_rules(raw)


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
    rate_reason: Optional[str] = None


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
    jita_share: float,
    mineral_buy_by_name: dict[str, Decimal],
    rate_reason: str | None = None,
    ore_unit_buy: Decimal | None = None,
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
    if ore_unit_buy is not None:
        ore_isk = float(ore_unit_buy) * quantity
        raw_isk = min(mineral_isk, ore_isk)
    else:
        raw_isk = mineral_isk
    line_total = raw_isk * jita_share
    unit_price = line_total / quantity if quantity else 0.0
    raw_unit = raw_isk / quantity if quantity else 0.0
    return PricedLine(
        type_id=type_id,
        name=name,
        quantity=quantity,
        category=BuybackCategory.ORE.value,
        rate=jita_share,
        unit_price=round(unit_price, 2),
        line_total=round(line_total, 2),
        accepted=True,
        refine_outputs={
            m: int(round(q)) for m, q in outputs.items() if round(q) > 0
        },
        jita_buy=round(raw_unit, 2),
        rate_reason=rate_reason,
    )


def price_flat_line(
    *,
    name: str,
    quantity: int,
    type_id: int | None,
    category: BuybackCategory,
    rate: float,
    buy_price: Decimal | None,
    rate_reason: str | None = None,
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
        rate_reason=rate_reason,
    )
