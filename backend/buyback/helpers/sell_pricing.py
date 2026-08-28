"""Sell prices for buyback purchase orders."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from eveonline.models import EveLocation
from market.helpers.pricing import get_history_averages_by_type_id
from market.models import EveMarketItemLocationPrice

from buyback.models import EveBuybackSettings, SellPriceBasis

TWOPLACES = Decimal("0.01")


def _live_jita_rows(type_ids: list[int]) -> dict[int, tuple]:
    if not type_ids:
        return {}
    baseline = EveLocation.objects.filter(price_baseline=True).first()
    if baseline is None:
        return {}
    rows = EveMarketItemLocationPrice.objects.filter(
        location=baseline,
        item_id__in=type_ids,
    ).values_list("item_id", "buy_price", "sell_price", "split_price")
    return {
        int(type_id): (buy_price, sell_price, split_price)
        for type_id, buy_price, sell_price, split_price in rows
    }


def _as_decimal(value) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def _basis_from_row(
    basis: str,
    buy_price,
    sell_price,
    split_price,
) -> Decimal | None:
    buy = _as_decimal(buy_price)
    sell = _as_decimal(sell_price)
    split = _as_decimal(split_price)
    if basis == SellPriceBasis.JITA_BUY:
        return buy or split
    if basis == SellPriceBasis.JITA_SELL:
        return sell or split
    if split is not None:
        return split
    if buy is not None and sell is not None:
        return (buy + sell) / Decimal("2")
    return buy or sell


def unit_prices_for_types(
    type_ids: list[int],
    *,
    settings: EveBuybackSettings | None = None,
) -> dict[int, Decimal]:
    """Unit sell prices: configured Jita basis, then Forge history."""
    if not type_ids:
        return {}
    unique_ids = list({int(tid) for tid in type_ids})
    loaded = settings or EveBuybackSettings.load()
    basis = loaded.sell_price_basis or SellPriceBasis.JITA_SPLIT
    markup = Decimal(str(loaded.sell_markup or 0))
    live = _live_jita_rows(unique_ids)
    prices: dict[int, Decimal] = {}
    for type_id in unique_ids:
        row = live.get(type_id)
        unit = _basis_from_row(basis, *(row or (None, None, None)))
        if unit is not None:
            prices[type_id] = unit
    missing = [tid for tid in unique_ids if tid not in prices]
    if missing and basis == SellPriceBasis.JITA_SPLIT:
        prices.update(get_history_averages_by_type_id(missing))
    if markup:
        factor = Decimal("1") + markup
        prices = {tid: value * factor for tid, value in prices.items()}
    return {
        tid: value.quantize(TWOPLACES, rounding=ROUND_HALF_UP)
        for tid, value in prices.items()
    }


def line_total(unit_price: Decimal, quantity: int) -> Decimal:
    return (unit_price * Decimal(quantity)).quantize(
        TWOPLACES, rounding=ROUND_HALF_UP
    )


def contract_total_isk(line_totals: list[Decimal]) -> int:
    total = sum(line_totals, Decimal("0"))
    return int(total.to_integral_value(rounding=ROUND_HALF_UP))
