"""Parse and apply landed unit prices for fitting buy order items."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from django.db import transaction

from buyback.helpers.classify import resolve_types_by_name
from market.models.fitting_buy_order import (
    FittingBuyOrder,
    FittingBuyOrderItem,
)


def _parse_decimal(token: str) -> Decimal | None:
    try:
        return Decimal(token.replace(",", "").strip())
    except (InvalidOperation, AttributeError):
        return None


def parse_unit_price_paste(paste: str) -> dict[str, Decimal]:
    result: dict[str, Decimal] = {}
    for raw_line in paste.splitlines():
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        if "\t" in raw_line:
            parts = [p.strip() for p in raw_line.split("\t") if p.strip()]
        else:
            parts = [
                p.strip() for p in re.split(r"\s{2,}", raw_line) if p.strip()
            ]
        if len(parts) < 2:
            continue
        price = None
        for i in range(len(parts) - 1, 0, -1):
            parsed = _parse_decimal(parts[i])
            if parsed is not None:
                price = parsed
                break
        if price is None:
            continue
        name = parts[0].strip()
        if name:
            result[name] = price
    return result


def apply_landed_prices(
    order: FittingBuyOrder, paste: str
) -> tuple[int, list[str]]:
    name_prices = parse_unit_price_paste(paste)
    resolved = resolve_types_by_name(list(name_prices.keys()))
    unresolved: list[str] = []
    items = {
        row.eve_type_id: row for row in order.items.select_related("eve_type")
    }
    name_to_item = {row.eve_type.name: row for row in items.values()}
    to_update: list[FittingBuyOrderItem] = []

    for name, price in name_prices.items():
        eve_type = resolved.get(name)
        row = items.get(eve_type.id) if eve_type is not None else None
        if row is None:
            row = name_to_item.get(name)
        if row is None:
            unresolved.append(name)
            continue
        row.unit_price = price
        to_update.append(row)

    if to_update:
        with transaction.atomic():
            FittingBuyOrderItem.objects.bulk_update(to_update, ["unit_price"])
    return len(to_update), list(dict.fromkeys(unresolved))
