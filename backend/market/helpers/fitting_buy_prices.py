"""Parse and apply landed unit prices for fitting buy order items.

Owners paste from EVE after buying. Two shapes show up:

* ``Name<TAB>unit price`` — one price per unit.
* ``Name<TAB>qty<TAB>total`` (Multibuy / wallet style) — the price is for
  the whole quantity bought, not one unit.

Storing a line total as ``unit_price`` inflates every per-hull cost by the
buy quantity, so pastes are normalised to a true unit price before saving.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from django.db import transaction

from buyback.helpers.classify import resolve_types_by_name
from market.models.fitting_buy_order import (
    FittingBuyOrder,
    FittingBuyOrderItem,
)

# A pasted number counts as "matching" a reference when it is within this
# band of it. Jita moves a little between the depth check and the buy.
PASTE_MATCH_LOW = Decimal("0.75")
PASTE_MATCH_HIGH = Decimal("1.33")
_INT_RE = re.compile(r"^\d{1,3}(?:[,.]\d{3})*$|^\d+$")


@dataclass
class PastedPrice:
    """One parsed paste line: price plus the quantity column, if any."""

    price: Decimal
    quantity: int | None = None


@dataclass
class PriceRow:
    """Inputs needed to decide whether one pasted price is a line total."""

    price: Decimal
    buy_qty: int
    jita_unit: Decimal | None
    pasted_qty: int | None = None

    @property
    def quantity(self) -> int:
        if self.pasted_qty and self.pasted_qty > 0:
            return self.pasted_qty
        return max(int(self.buy_qty or 0), 0)


def _parse_decimal(token: str) -> Decimal | None:
    try:
        return Decimal(token.replace(",", "").strip())
    except (InvalidOperation, AttributeError):
        return None


def _parse_int(token: str) -> int | None:
    cleaned = token.replace(" ", "")
    if not _INT_RE.match(cleaned):
        return None
    try:
        return int(cleaned.replace(",", "").replace(".", ""))
    except ValueError:
        return None


def _split_columns(raw_line: str) -> list[str]:
    if "\t" in raw_line:
        return [p.strip() for p in raw_line.split("\t") if p.strip()]
    return [p.strip() for p in re.split(r"\s{2,}", raw_line) if p.strip()]


def _within(value: Decimal, reference: Decimal) -> bool:
    if reference <= 0 or value <= 0:
        return False
    ratio = value / reference
    return PASTE_MATCH_LOW <= ratio <= PASTE_MATCH_HIGH


def _price_from_columns(columns: list[str]) -> PastedPrice | None:
    """Trailing numeric columns → price (last) and quantity (first int)."""
    numeric: list[str] = []
    for token in reversed(columns[1:]):
        if _parse_decimal(token) is None:
            break
        numeric.insert(0, token)
    if not numeric:
        return None
    price = _parse_decimal(numeric[-1])
    if price is None:
        return None
    quantity = None
    if len(numeric) >= 2:
        quantity = _parse_int(numeric[0])
        if len(numeric) >= 3 and quantity:
            # qty, unit, total → prefer the explicit unit column when the
            # arithmetic checks out.
            unit = _parse_decimal(numeric[1])
            if unit is not None and _within(unit * quantity, price):
                return PastedPrice(price=unit, quantity=None)
    return PastedPrice(price=price, quantity=quantity)


def parse_price_paste(paste: str) -> dict[str, PastedPrice]:
    result: dict[str, PastedPrice] = {}
    for raw_line in paste.splitlines():
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        parts = _split_columns(raw_line)
        if len(parts) < 2:
            continue
        pasted = _price_from_columns(parts)
        if pasted is None:
            continue
        name = parts[0].strip()
        if name:
            result[name] = pasted
    return result


def parse_unit_price_paste(paste: str) -> dict[str, Decimal]:
    """Backwards-compatible view: name → pasted price (unit or total)."""
    return {
        name: pasted.price for name, pasted in parse_price_paste(paste).items()
    }


def pasted_prices_are_totals(rows: list[PriceRow]) -> bool:
    """
    Decide whether a paste holds line totals instead of unit prices.

    One paste is either all-units or all-totals, so this votes across the
    rows that can tell the two apart (quantity > 1 and a Jita reference).
    A quantity column with no Jita reference is read as a Multibuy total.
    """
    total_votes = 0
    unit_votes = 0
    qty_column_rows = 0
    for row in rows:
        qty = row.quantity
        if qty <= 1:
            continue
        if row.jita_unit is None or row.jita_unit <= 0:
            if row.pasted_qty:
                qty_column_rows += 1
            continue
        looks_unit = _within(row.price, row.jita_unit)
        looks_total = _within(row.price, row.jita_unit * qty)
        if looks_total and not looks_unit:
            total_votes += 1
        elif looks_unit and not looks_total:
            unit_votes += 1
    if total_votes or unit_votes:
        return total_votes > unit_votes
    return qty_column_rows > 0


def normalize_unit_price(row: PriceRow, *, totals: bool) -> Decimal:
    """Unit price for one pasted row given the paste-wide totals decision."""
    if not totals or row.quantity <= 1:
        return row.price
    return (row.price / Decimal(row.quantity)).quantize(Decimal("0.01"))


def apply_landed_prices(
    order: FittingBuyOrder, paste: str
) -> tuple[int, list[str]]:
    name_prices = parse_price_paste(paste)
    resolved = resolve_types_by_name(list(name_prices.keys()))
    unresolved: list[str] = []
    items = {
        row.eve_type_id: row for row in order.items.select_related("eve_type")
    }
    name_to_item = {row.eve_type.name: row for row in items.values()}
    matched: list[tuple[FittingBuyOrderItem, PriceRow]] = []

    for name, pasted in name_prices.items():
        eve_type = resolved.get(name)
        row = items.get(eve_type.id) if eve_type is not None else None
        if row is None:
            row = name_to_item.get(name)
        if row is None:
            unresolved.append(name)
            continue
        matched.append(
            (
                row,
                PriceRow(
                    price=pasted.price,
                    buy_qty=int(row.buy_qty or 0),
                    jita_unit=(
                        Decimal(row.jita_sell_min)
                        if row.jita_sell_min is not None
                        else None
                    ),
                    pasted_qty=pasted.quantity,
                ),
            )
        )

    totals = pasted_prices_are_totals([price for _, price in matched])
    to_update: list[FittingBuyOrderItem] = []
    for row, price in matched:
        row.unit_price = normalize_unit_price(price, totals=totals)
        to_update.append(row)

    if to_update:
        with transaction.atomic():
            FittingBuyOrderItem.objects.bulk_update(to_update, ["unit_price"])
    return len(to_update), list(dict.fromkeys(unresolved))
