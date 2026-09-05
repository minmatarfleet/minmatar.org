"""Per-hull landed cost and recommended contract prices for fitting buy orders."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable

from django.db.models import Prefetch
from eveuniverse.models import EveType

from industry.models import IndustryOrderItem, IndustryOrderItemAssignment
from market.helpers.fitting_buy_fit_copies import build_fit_copies_by_line
from market.helpers.fitting_buy_plan import (
    apply_type_swaps,
    line_type_quantities,
)
from market.helpers.pricing import get_prices_by_type_id
from market.models.fitting_buy_order import (
    FittingBuyOrder,
    FittingBuyOrderLine,
)


def _isk_str(value: Decimal | int | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, int):
        return str(value)
    quantized = value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return str(int(quantized))


def _markup(base: Decimal | None, factor: Decimal) -> str | None:
    if base is None:
        return None
    return _isk_str(base * factor)


def _cost_value(amount: Decimal, *, complete: bool) -> Decimal | None:
    if complete or amount > 0:
        return amount
    return None


@dataclass(frozen=True)
class IndustryAsk:
    type_id: int
    unit_price: Decimal
    order_id: int
    public_short_code: str


def _line_ask_decimal(item: IndustryOrderItem) -> Decimal | None:
    unit = item.target_unit_price
    if unit is None:
        for assignment in item.assignments.all():
            if assignment.target_unit_price is not None:
                unit = assignment.target_unit_price
                break
    if unit is None:
        return None
    return Decimal(unit)


def latest_open_industry_asks(
    type_ids: Iterable[int],
) -> dict[int, IndustryAsk]:
    """Latest unfulfilled industry ask per type (order-item, else assignment)."""
    unique_ids = list({int(tid) for tid in type_ids if tid})
    if not unique_ids:
        return {}

    assignment_qs = IndustryOrderItemAssignment.objects.only(
        "id",
        "order_item_id",
        "target_unit_price",
    )
    items = (
        IndustryOrderItem.objects.filter(
            eve_type_id__in=unique_ids,
            order__fulfilled_at__isnull=True,
        )
        .select_related("order")
        .prefetch_related(Prefetch("assignments", queryset=assignment_qs))
        .order_by("-order__created_at", "-order_id", "id")
    )

    result: dict[int, IndustryAsk] = {}
    for item in items:
        type_id = int(item.eve_type_id)
        if type_id in result:
            continue
        ask = _line_ask_decimal(item)
        if ask is None:
            continue
        order = item.order
        result[type_id] = IndustryAsk(
            type_id=type_id,
            unit_price=ask,
            order_id=order.id,
            public_short_code=order.public_short_code or "",
        )
    return result


def _stock_covered_type_ids(order: FittingBuyOrder) -> set[int]:
    """Types fully filled from on-hand stock (nothing left to buy)."""
    return {
        int(row.eve_type_id)
        for row in order.items.all()
        if int(row.buy_qty or 0) <= 0
    }


def _preferred_for_variant(
    allocations: dict,
    line: FittingBuyOrderLine,
    variant_type_id: int,
) -> int | None:
    """Find preferred type_id that was allocated onto this variant."""
    for preferred_key, entries in (allocations or {}).items():
        preferred_id = int(preferred_key)
        for entry in entries or []:
            if int(entry.get("type_id") or 0) == variant_type_id:
                return preferred_id
    for swap in line.swaps or []:
        preferred = int(swap.get("preferred_type_id") or 0)
        substitute = int(swap.get("substitute_type_id") or 0)
        if substitute == variant_type_id and preferred:
            return preferred
    return None


def _per_ship_for_copy(
    *,
    original_per_ship: dict[int, int],
    line: FittingBuyOrderLine,
    copy: dict,
    allocations: dict,
) -> dict[int, int]:
    if not copy.get("is_swapped"):
        return dict(original_per_ship)

    copy_swaps = copy.get("swaps")
    if copy_swaps:
        return apply_type_swaps(original_per_ship, copy_swaps)

    variant_type_id = copy.get("variant_type_id")
    if variant_type_id:
        preferred = None
        for swap in line.swaps or []:
            preferred = int(swap.get("preferred_type_id") or 0)
            if preferred:
                break
        if preferred is None:
            preferred = _preferred_for_variant(
                allocations, line, int(variant_type_id)
            )
        if preferred:
            return apply_type_swaps(
                original_per_ship,
                [
                    {
                        "preferred_type_id": preferred,
                        "substitute_type_id": int(variant_type_id),
                    }
                ],
            )
        return dict(original_per_ship)

    return apply_type_swaps(original_per_ship, line.swaps)


def build_contract_prices(order: FittingBuyOrder) -> list[dict]:  # noqa: C901
    """
    Recommended contract prices per fit copy (original / swapped / variant).

    Landed unit cost: pasted FittingBuyOrderItem.unit_price, else latest open
    industry ask. Types fully filled from on-hand stock skip industry and use
    Jita sell. Hull is always included even when include_hull is false; if the
    hull still has no landed/industry price, Jita sell is used. Fitting cost
    and total cost are per hull.
    """
    order_lines = list(
        order.lines.select_related("fitting").order_by("sort_order", "id")
    )
    if not order_lines:
        return []

    fit_copies = build_fit_copies_by_line(order, order_lines)
    original_boms = {
        bom.line_id: bom
        for bom in line_type_quantities(
            order_lines,
            include_hull=True,
            apply_line_swaps=False,
        )
    }

    pasted = {
        int(row.eve_type_id): Decimal(row.unit_price)
        for row in order.items.all()
        if row.unit_price is not None
    }
    stock_covered = _stock_covered_type_ids(order)

    all_type_ids: set[int] = set()
    allocations = order.shopping_allocations or {}
    per_copy_boms: list[tuple[FittingBuyOrderLine, dict, dict[int, int]]] = []
    for line in order_lines:
        original = original_boms.get(line.id)
        if original is None:
            continue
        copies = fit_copies.get(line.id) or [
            {
                "quantity": int(line.quantity),
                "eft": line.fitting.eft_format or "",
                "is_swapped": False,
                "variant_type_id": None,
                "variant_name": "",
            }
        ]
        for copy in copies:
            per_ship = _per_ship_for_copy(
                original_per_ship=original.per_ship,
                line=line,
                copy=copy,
                allocations=allocations,
            )
            all_type_ids.update(per_ship)
            per_copy_boms.append((line, copy, per_ship))

    industry_asks = latest_open_industry_asks(
        all_type_ids - set(pasted) - stock_covered
    )
    jita_prices = get_prices_by_type_id(list(all_type_ids))
    type_names = dict(
        EveType.objects.filter(id__in=all_type_ids).values_list("id", "name")
    )
    ship_ids = {
        int(line.fitting.ship_id)
        for line, copy, per_ship in per_copy_boms
        if line.fitting.ship_id
    }
    ship_names = dict(
        EveType.objects.filter(id__in=ship_ids).values_list("id", "name")
    )

    rows: list[dict] = []
    for line, copy, per_ship in per_copy_boms:
        ship_id = int(line.fitting.ship_id) if line.fitting.ship_id else 0
        hull_cost = Decimal("0")
        fitting_cost = Decimal("0")
        hull_complete = ship_id not in per_ship
        fitting_complete = True
        has_fitting_types = False
        landed_complete = True
        missing: list[str] = []
        industry_sources: list[dict] = []
        used_industry_types: set[int] = set()
        hull_cost_source = ""
        hull_industry_order_id: int | None = None
        hull_industry_short_code = ""
        hull_from_jita = False

        for type_id, qty in sorted(per_ship.items()):
            # qty is items on one hull — never multiply by line/copy quantity.
            is_hull = type_id == ship_id
            if not is_hull:
                has_fitting_types = True
            unit = pasted.get(type_id)
            source = None
            from_jita = False
            if unit is None and type_id not in stock_covered:
                ask = industry_asks.get(type_id)
                if ask is not None:
                    unit = ask.unit_price
                    source = ask
            if unit is None and (is_hull or type_id in stock_covered):
                guide = jita_prices.get(type_id)
                if guide is not None:
                    unit = Decimal(guide)
                    from_jita = True
            if unit is None:
                landed_complete = False
                missing.append(type_names.get(type_id, str(type_id)))
                if is_hull:
                    hull_complete = False
                else:
                    fitting_complete = False
                continue
            line_cost = unit * Decimal(qty)
            if is_hull:
                hull_cost += line_cost
                hull_complete = True
                if source is not None:
                    hull_cost_source = "industry"
                    hull_industry_order_id = source.order_id
                    hull_industry_short_code = source.public_short_code
                elif from_jita:
                    hull_cost_source = "jita"
                    hull_from_jita = True
                else:
                    hull_cost_source = "landed"
            else:
                fitting_cost += line_cost
            if source is not None and type_id not in used_industry_types:
                used_industry_types.add(type_id)
                industry_sources.append(
                    {
                        "type_id": type_id,
                        "type_name": type_names.get(type_id, str(type_id)),
                        "unit_price": _isk_str(source.unit_price),
                        "order_id": source.order_id,
                        "public_short_code": source.public_short_code,
                    }
                )

        if not has_fitting_types:
            fitting_complete = True

        landed = hull_cost + fitting_cost
        jita_total = Decimal("0")
        jita_complete = True
        for type_id, qty in per_ship.items():
            guide = jita_prices.get(type_id)
            if guide is None:
                jita_complete = False
                continue
            jita_total += Decimal(guide) * Decimal(qty)

        hull_value = _cost_value(hull_cost, complete=hull_complete)
        fitting_value = _cost_value(fitting_cost, complete=fitting_complete)
        landed_value = _cost_value(landed, complete=landed_complete)
        jita_value: Decimal | None = jita_total if jita_complete else None

        rows.append(
            {
                "line_id": line.id,
                "fitting_id": line.fitting_id,
                "fitting_name": line.fitting.name,
                "ship_id": line.fitting.ship_id,
                "ship_name": ship_names.get(
                    int(line.fitting.ship_id),
                    str(line.fitting.ship_id),
                ),
                "eft": str(copy.get("eft") or ""),
                "quantity": int(copy.get("quantity") or 0),
                "is_swapped": bool(copy.get("is_swapped")),
                "variant_name": str(copy.get("variant_name") or ""),
                "hull_cost": _isk_str(hull_value),
                "hull_cost_from_jita": hull_from_jita,
                "hull_cost_source": hull_cost_source,
                "hull_cost_industry_order_id": hull_industry_order_id,
                "hull_cost_industry_short_code": hull_industry_short_code,
                "fitting_cost": _isk_str(fitting_value),
                "landed_per_ship": _isk_str(landed_value),
                "landed_complete": landed_complete,
                "missing_type_names": missing,
                "landed_plus_20": _markup(landed_value, Decimal("1.20")),
                "jita_sell_per_ship": _isk_str(jita_value),
                "jita_plus_20": _markup(jita_value, Decimal("1.20")),
                "industry_sources": industry_sources,
            }
        )
    return rows
