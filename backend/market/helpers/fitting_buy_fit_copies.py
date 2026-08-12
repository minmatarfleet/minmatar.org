"""Expand fitting buy lines into per-variant fit copies for the Fits list."""

from __future__ import annotations

from collections import defaultdict

from eveuniverse.models import EveType

from market.helpers.fitting_buy_allocations import (
    AllocationError,
    normalize_entries,
)
from market.helpers.fitting_buy_eft import (
    apply_swaps_to_eft,
    effective_eft_for_line,
)
from market.helpers.fitting_buy_plan import line_type_quantities
from market.models.fitting_buy_order import (
    FittingBuyOrder,
    FittingBuyOrderLine,
)


def _type_names(type_ids: set[int]) -> dict[int, str]:
    if not type_ids:
        return {}
    return dict(
        EveType.objects.filter(id__in=type_ids).values_list("id", "name")
    )


def _copies_from_swap_split(
    line: FittingBuyOrderLine,
    *,
    original_eft: str,
    swapped_eft: str,
) -> list[dict]:
    quantity = int(line.quantity)
    swaps = line.swaps or []
    if not swaps:
        return [
            {
                "quantity": quantity,
                "eft": original_eft,
                "is_swapped": False,
                "variant_type_id": None,
                "variant_name": "",
            }
        ]
    raw_swap_qty = line.swap_hull_qty
    if raw_swap_qty is None:
        original_quantity = 0
        swapped_quantity = quantity
    else:
        swapped_quantity = max(0, min(quantity, int(raw_swap_qty)))
        original_quantity = quantity - swapped_quantity
    copies: list[dict] = []
    if original_quantity > 0:
        copies.append(
            {
                "quantity": original_quantity,
                "eft": original_eft,
                "is_swapped": False,
                "variant_type_id": None,
                "variant_name": "",
            }
        )
    if swapped_quantity > 0:
        copies.append(
            {
                "quantity": swapped_quantity,
                "eft": swapped_eft,
                "is_swapped": True,
                "variant_type_id": None,
                "variant_name": "",
            }
        )
    return copies


def _distribute_qty(
    total: int, weights: list[tuple[int, int]]
) -> dict[int, int]:
    """Largest-remainder share of total across (id, weight) rows."""
    if total <= 0 or not weights:
        return {}
    weight_sum = sum(weight for _, weight in weights)
    if weight_sum <= 0:
        return {}
    floors: dict[int, int] = {}
    remainders: list[tuple[float, int]] = []
    assigned = 0
    for row_id, weight in weights:
        exact = total * weight / weight_sum
        floor = int(exact)
        floors[row_id] = floor
        assigned += floor
        remainders.append((exact - floor, row_id))
    leftover = total - assigned
    remainders.sort(key=lambda item: (-item[0], item[1]))
    for _, row_id in remainders[:leftover]:
        floors[row_id] += 1
    return floors


def _distribute_allocation_modules(
    order_lines: list[FittingBuyOrderLine],
    *,
    include_hull: bool,
    preferred_id: int,
    entries: list[dict],
) -> dict[int, dict[int, int]]:
    """Share global allocation module qtys across lines that need preferred.

    Returns {line_id: {type_id: module_qty}}.
    """
    unswapped = {
        bom.line_id: bom
        for bom in line_type_quantities(
            order_lines,
            include_hull=include_hull,
            apply_line_swaps=False,
        )
    }
    weights: list[tuple[int, int]] = []
    for line in order_lines:
        bom = unswapped.get(line.id)
        if not bom:
            continue
        per = int(bom.per_ship.get(preferred_id, 0) or 0)
        if per <= 0:
            continue
        weights.append((line.id, int(line.quantity) * per))
    if not weights:
        return {}

    distributed: dict[int, dict[int, int]] = defaultdict(dict)
    for entry in entries:
        type_id = int(entry["type_id"])
        shares = _distribute_qty(int(entry["qty"]), weights)
        for line_id, qty in shares.items():
            if qty <= 0:
                continue
            distributed[line_id][type_id] = (
                distributed[line_id].get(type_id, 0) + qty
            )
    return dict(distributed)


def _variant_allocation_entries(
    allocations: dict,
) -> tuple[dict[int, list[dict]], set[int]]:
    """Parse shopping_allocations that include at least one non-preferred."""
    entries_by_preferred: dict[int, list[dict]] = {}
    type_ids: set[int] = set()
    for key, raw in allocations.items():
        preferred_id = int(key)
        try:
            entries = normalize_entries(raw or [])
        except AllocationError:
            continue
        if not entries:
            continue
        if not any(entry["type_id"] != preferred_id for entry in entries):
            continue
        entries_by_preferred[preferred_id] = entries
        type_ids.add(preferred_id)
        for entry in entries:
            type_ids.add(int(entry["type_id"]))
    return entries_by_preferred, type_ids


def _swap_type_ids(order_lines: list[FittingBuyOrderLine]) -> set[int]:
    type_ids: set[int] = set()
    for line in order_lines:
        for swap in line.swaps or []:
            preferred = int(swap.get("preferred_type_id") or 0)
            substitute = int(swap.get("substitute_type_id") or 0)
            if preferred:
                type_ids.add(preferred)
            if substitute:
                type_ids.add(substitute)
    return type_ids


def _pick_allocated_preferred(
    bom, preferred_modules: dict[int, dict[int, int]]
) -> tuple[int | None, dict[int, int]]:
    for preferred_id, qtys in preferred_modules.items():
        per = int(bom.per_ship.get(preferred_id, 0) or 0)
        if per <= 0:
            continue
        return preferred_id, qtys
    return None, {}


def _copies_from_allocation(
    line: FittingBuyOrderLine,
    *,
    bom,
    preferred_id: int,
    module_qtys: dict[int, int],
    original_eft: str,
    names: dict[int, str],
) -> list[dict]:
    per = int(bom.per_ship.get(preferred_id, 0) or 0)
    original_ships = 0
    variant_copies: list[dict] = []
    preferred_key = preferred_id
    ordered = sorted(
        module_qtys.items(),
        key=lambda item: (item[0] == preferred_key, item[0]),
    )
    for type_id, module_qty in ordered:
        if per <= 0:
            continue
        ships = int(module_qty) // per
        if ships <= 0:
            continue
        if type_id == preferred_key:
            original_ships += ships
            continue
        eft = apply_swaps_to_eft(
            original_eft,
            [
                {
                    "preferred_type_id": preferred_key,
                    "substitute_type_id": type_id,
                }
            ],
            names,
        )
        variant_copies.append(
            {
                "quantity": ships,
                "eft": eft,
                "is_swapped": True,
                "variant_type_id": type_id,
                "variant_name": names.get(type_id, ""),
            }
        )

    assigned_ships = original_ships + sum(
        copy["quantity"] for copy in variant_copies
    )
    remaining = int(line.quantity) - assigned_ships
    if remaining > 0:
        original_ships += remaining

    copies: list[dict] = []
    if original_ships > 0:
        copies.append(
            {
                "quantity": original_ships,
                "eft": original_eft,
                "is_swapped": False,
                "variant_type_id": None,
                "variant_name": "",
            }
        )
    copies.extend(variant_copies)
    return copies


def build_fit_copies_by_line(
    order: FittingBuyOrder,
    order_lines: list[FittingBuyOrderLine],
) -> dict[int, list[dict]]:
    """Per-line fit copies: allocation variants first, else swap split."""
    allocations = order.shopping_allocations or {}
    unswapped_boms = {
        bom.line_id: bom
        for bom in line_type_quantities(
            order_lines,
            include_hull=order.include_hull,
            apply_line_swaps=False,
        )
    }

    alloc_entries_by_preferred, type_ids = _variant_allocation_entries(
        allocations
    )
    type_ids |= _swap_type_ids(order_lines)
    names = _type_names(type_ids)

    line_modules: dict[int, dict[int, dict[int, int]]] = defaultdict(dict)
    for preferred_id, entries in alloc_entries_by_preferred.items():
        distributed = _distribute_allocation_modules(
            order_lines,
            include_hull=order.include_hull,
            preferred_id=preferred_id,
            entries=entries,
        )
        for line_id, qtys in distributed.items():
            line_modules[line_id][preferred_id] = qtys

    result: dict[int, list[dict]] = {}
    for line in order_lines:
        original_eft = line.fitting.eft_format or ""
        swapped_eft = effective_eft_for_line(line, type_names=names)
        bom = unswapped_boms.get(line.id)
        preferred_modules = line_modules.get(line.id) or {}
        chosen_preferred, chosen_qtys = (
            _pick_allocated_preferred(bom, preferred_modules)
            if bom and preferred_modules
            else (None, {})
        )

        if chosen_preferred is not None and chosen_qtys and bom is not None:
            copies = _copies_from_allocation(
                line,
                bom=bom,
                preferred_id=chosen_preferred,
                module_qtys=chosen_qtys,
                original_eft=original_eft,
                names=names,
            )
            result[line.id] = copies or _copies_from_swap_split(
                line, original_eft=original_eft, swapped_eft=swapped_eft
            )
            continue

        result[line.id] = _copies_from_swap_split(
            line, original_eft=original_eft, swapped_eft=swapped_eft
        )

    return result
