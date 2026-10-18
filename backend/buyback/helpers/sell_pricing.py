"""Sell prices for buyback purchase orders."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from market.helpers.pricing import (
    baseline_book,
    get_history_averages_by_type_id,
)

from buyback.models import EveBuybackSettings, SellPriceBasis

TWOPLACES = Decimal("0.01")


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
    """
    Unit sell prices: configured Jita basis (with split as its fallback),
    then Forge history for every basis. Types with no price at all are
    omitted; callers must not sell those at 0 ISK.
    """
    if not type_ids:
        return {}
    unique_ids = list({int(tid) for tid in type_ids})
    loaded = settings or EveBuybackSettings.load()
    basis = loaded.sell_price_basis or SellPriceBasis.JITA_SPLIT
    markup = Decimal(str(loaded.sell_markup or 0))
    live = baseline_book(unique_ids)
    prices: dict[int, Decimal] = {}
    for type_id in unique_ids:
        row = live.get(type_id)
        unit = (
            _basis_from_row(basis, row.buy, row.sell, row.split)
            if row is not None
            else None
        )
        if unit is not None:
            prices[type_id] = unit
    # Same rule as the appraisal side (get_baseline_buy_prices): a type with
    # no usable live value at the baseline falls back to Forge history
    # (then EveMarketPrice), whatever the basis.
    missing = [tid for tid in unique_ids if tid not in prices]
    if missing:
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
