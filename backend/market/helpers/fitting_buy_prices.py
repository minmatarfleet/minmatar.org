"""Parse and apply landed unit prices for fitting buy order items.

Owners paste from EVE after buying. The shapes that show up:

* ``Name<TAB>unit price`` — one price per unit.
* ``Name<TAB>qty<TAB>total`` — Multibuy / wallet, the price is the line.
* ``Name qty total`` — the same columns separated by single spaces.
* A wallet row whose first column is the date, with the item name later.
* ``Bought {qty} units of {name} for {total} ISK``.

Numbers may use US (``1,234.56``) or EU (``1.234,56``) grouping, and a
trailing ``ISK``. A line total is divided down to a unit price before
saving so per-hull costs are not inflated by the buy quantity.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from django.db import transaction

from eveonline.helpers.universe import resolve_types_by_name
from market.models.fitting_buy_order import (
    FittingBuyOrder,
    FittingBuyOrderItem,
)

# A pasted number counts as "matching" a reference when it is within this
# band of it. Jita moves a little between the depth check and the buy.
PASTE_MATCH_LOW = Decimal("0.75")
PASTE_MATCH_HIGH = Decimal("1.33")
_INT_RE = re.compile(r"^\d{1,3}(?:[,.]\d{3})*$|^\d+$")
_NUMBER_RE = re.compile(r"^[+-]?\d[\d.,]*$")
_DATE_RE = re.compile(
    r"^\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2}(?:[ T]\d{1,2}:\d{2}(?::\d{2})?)?$"
)
_TIME_RE = re.compile(r"^\d{1,2}:\d{2}(?::\d{2})?$")
_ISK_RE = re.compile(r"(?i)\s*isk\s*$")
_BOUGHT_FOR_RE = re.compile(
    r"(?i)\bbought\s+(?P<qty>\d[\d,.]*)\b"
    r"(?:\s+units?\s+of\b)?.*?\bfor\s+(?P<total>\d[\d,.]*)"
)
_TRAILING_QTY_RE = re.compile(r"^(?P<name>.+?)\s+(?P<qty>\d[\d,.]*)\s*$")
_IGNORABLE = frozenset({"isk", "each", "ea"})
_HEADER_WORDS = frozenset(
    {
        "item",
        "name",
        "type",
        "quantity",
        "qty",
        "price",
        "unit",
        "total",
        "volume",
        "group",
        "category",
        "date",
        "client",
        "location",
        "where",
    }
)


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


def _clean_token(token: str) -> str:
    return (token or "").replace("\u00a0", " ").strip().strip(",;").strip()


def _parse_decimal(token: str) -> Decimal | None:
    """US or EU amount, optional trailing ISK. Dates and times are not amounts."""
    text = _ISK_RE.sub("", _clean_token(token).replace(" ", ""))
    if not text or _DATE_RE.match(text) or _TIME_RE.match(text):
        return None
    if not _NUMBER_RE.match(text):
        return None
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        # ``1234,56`` is a decimal; ``1,234,567`` is thousands.
        if re.fullmatch(r"[+-]?\d+,\d{1,2}", text):
            text = text.replace(",", ".")
        else:
            text = text.replace(",", "")
    elif text.count(".") > 1:
        text = text.replace(".", "")
    try:
        value = Decimal(text)
    except InvalidOperation:
        return None
    if value < 0:
        value = -value
    return value


def _parse_int(token: str) -> int | None:
    cleaned = _clean_token(token).replace(" ", "")
    if not _INT_RE.match(cleaned):
        return None
    try:
        return int(cleaned.replace(",", "").replace(".", ""))
    except ValueError:
        return None


def _is_ignorable(token: str) -> bool:
    return _clean_token(token).casefold() in _IGNORABLE


def _is_header(line: str) -> bool:
    tokens = [
        _clean_token(part).casefold()
        for part in re.split(r"[\t|;]+|\s{2,}", line)
        if _clean_token(part)
    ]
    if len(tokens) < 2:
        return False
    hits = sum(1 for token in tokens if token in _HEADER_WORDS)
    return hits >= 2


def _is_noise_name(name: str) -> bool:
    text = _clean_token(name)
    if not text:
        return True
    if _DATE_RE.match(text) or _TIME_RE.match(text):
        return True
    return _parse_decimal(text) is not None and not re.search(
        r"[A-Za-z]", text
    )


def _split_columns(raw_line: str) -> list[str]:
    line = raw_line.replace("\u00a0", " ").strip()
    # ``Name, 10, 1,234.56`` from a spreadsheet. Thousands separators have
    # no space after the comma, so this does not split those.
    if "\t" not in line and ";" not in line and ", " in line:
        line = line.replace(", ", "\t")
    if "\t" in line or "|" in line:
        return [
            part.strip() for part in re.split(r"[\t|]+", line) if part.strip()
        ]
    if ";" in line:
        parts = [part.strip() for part in line.split(";") if part.strip()]
        if len(parts) >= 2:
            return parts
    spaced = [
        part.strip() for part in re.split(r"\s{2,}", line) if part.strip()
    ]
    if len(spaced) >= 2:
        return spaced
    name, numbers = _peel_trailing_numbers(line)
    # One trailing integer is a Multibuy quantity (``Name 10``), not a price.
    if len(numbers) >= 2:
        return [name, *numbers]
    return [line] if line else []


def _peel_trailing_numbers(line: str) -> tuple[str, list[str]]:
    tokens = line.split()
    while tokens and _is_ignorable(tokens[-1]):
        tokens.pop()
    numbers: list[str] = []
    while tokens and _parse_decimal(tokens[-1]) is not None:
        numbers.append(tokens.pop())
    if not tokens or not numbers:
        return line, []
    return " ".join(tokens).strip(" ,;"), list(reversed(numbers))


def _strip_trailing_qty(name: str) -> tuple[str, int | None]:
    """``Damage Control II 10`` left in the name cell of a spreadsheet."""
    match = _TRAILING_QTY_RE.match(name.strip())
    if not match:
        return name.strip(), None
    qty = _parse_int(match.group("qty"))
    if qty is None:
        return name.strip(), None
    stripped = match.group("name").strip()
    if not stripped or not re.search(r"[A-Za-z]", stripped):
        return name.strip(), None
    return stripped, qty


def _within(value: Decimal, reference: Decimal) -> bool:
    if reference <= 0 or value <= 0:
        return False
    ratio = value / reference
    return PASTE_MATCH_LOW <= ratio <= PASTE_MATCH_HIGH


def _price_from_columns(columns: list[str]) -> PastedPrice | None:
    """Numeric columns after the name → price (last) and quantity (first)."""
    numeric: list[str] = []
    for token in reversed(columns[1:]):
        if _is_ignorable(token) or _parse_decimal(token) is None:
            continue
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


def _find_known_name(line: str, known_names: list[str]) -> str | None:
    """Longest order item name that appears as its own phrase in ``line``."""
    folded = line.casefold()
    for name in known_names:
        needle = name.casefold()
        if len(needle) < 3:
            continue
        start = 0
        while True:
            index = folded.find(needle, start)
            if index < 0:
                break
            end = index + len(needle)
            before = folded[index - 1] if index else ""
            after = folded[end] if end < len(folded) else ""
            if _name_boundary(before) and _name_boundary(after):
                return name
            start = index + 1
    return None


def _name_boundary(char: str) -> bool:
    return char == "" or not (char.isalnum() or char == "_")


def _line_cells(line: str) -> list[str] | None:
    """Tab, pipe, or semicolon cells. ``None`` when the line is not a grid."""
    if "\t" in line or "|" in line:
        return [
            part.strip() for part in re.split(r"[\t|]+", line) if part.strip()
        ]
    if ";" in line:
        parts = [part.strip() for part in line.split(";") if part.strip()]
        if len(parts) >= 2:
            return parts
    return None


def _cell_amount(cell: str) -> str | None:
    """One amount cell. A station name such as ``Jita IV - Moon 4`` is not one."""
    text = _clean_token(cell)
    if not text or _is_ignorable(text):
        return None
    bare = _ISK_RE.sub("", text).strip()
    if re.search(r"[A-Za-z]", bare):
        return None
    if _parse_decimal(text) is None:
        return None
    return text


def _looks_like_money(token: str) -> bool:
    text = _ISK_RE.sub("", _clean_token(token))
    return bool(re.search(r"[,.]", text) or "isk" in token.casefold())


def _column_price(
    parts: list[str],
) -> tuple[str, PastedPrice] | None:
    if len(parts) < 2:
        return None
    name, extra_qty = _strip_trailing_qty(parts[0])
    pasted = _price_from_columns([name, *parts[1:]])
    if pasted is None or not name or _is_noise_name(name):
        return None
    if extra_qty and pasted.quantity is None:
        pasted = PastedPrice(price=pasted.price, quantity=extra_qty)
    return name, pasted


def _known_name_price(
    line: str, known_names: list[str]
) -> tuple[str, PastedPrice] | None:
    found = _find_known_name(line, known_names)
    if not found:
        return None
    bought = _BOUGHT_FOR_RE.search(line)
    if bought:
        qty = _parse_int(bought.group("qty"))
        total = _parse_decimal(bought.group("total"))
        if qty and total is not None:
            return found, PastedPrice(price=total, quantity=qty)
    cells = _line_cells(line)
    if cells is not None:
        numbers = [amount for cell in cells if (amount := _cell_amount(cell))]
        # A lone integer is the Multibuy quantity, not the price.
        if len(numbers) == 1 and not _looks_like_money(numbers[0]):
            return None
    else:
        _, numbers = _peel_trailing_numbers(line)
        if len(numbers) < 2:
            return None
    if not numbers:
        return None
    pasted = _price_from_columns([found, *numbers])
    if pasted is None:
        return None
    return found, pasted


def parse_price_paste(
    paste: str, known_names: list[str] | None = None
) -> dict[str, PastedPrice]:
    """Map item name → pasted price. ``known_names`` finds items in wallet rows."""
    known = sorted(
        {name for name in (known_names or []) if name},
        key=len,
        reverse=True,
    )
    known_folded = {name.casefold() for name in known}
    result: dict[str, PastedPrice] = {}
    text = (paste or "").replace("\r\n", "\n").replace("\r", "\n")
    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not line or _is_header(line):
            continue
        column = _column_price(_split_columns(line))
        if column is not None and (
            not known_folded or column[0].casefold() in known_folded
        ):
            result[column[0]] = column[1]
            continue
        if known:
            known_hit = _known_name_price(line, known)
            if known_hit is not None:
                result[known_hit[0]] = known_hit[1]
                continue
        if column is not None:
            result[column[0]] = column[1]
    return result


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
    items = {
        row.eve_type_id: row for row in order.items.select_related("eve_type")
    }
    name_prices = parse_price_paste(
        paste,
        known_names=[
            row.eve_type.name for row in items.values() if row.eve_type_id
        ],
    )
    resolved = resolve_types_by_name(
        list(name_prices.keys()), case_insensitive=True
    )
    unresolved: list[str] = []
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
