"""Apply module swaps on fitting buy order lines.

When Jita/stock can only cover part of a line, applying a swap keeps the
original fit for the completable hulls (`quantity - swap_hull_qty`) and
records the modified EFT for the remainder (`swap_hull_qty`).
"""

from __future__ import annotations

from market.helpers.fitting_buy_plan import (
    line_type_quantities,
    sync_order_items,
)
from market.models.fitting_buy_order import (
    FittingBuyOrder,
    FittingBuyOrderItem,
    FittingBuyOrderLine,
)


def _available_modules(item: FittingBuyOrderItem | None) -> int | None:
    """Modules on hand + buyable from Jita for one shopping row.

    Returns None when Jita has not been checked yet (unknown depth).
    """
    if item is None:
        return 0
    if item.jita_sell_volume is None:
        return None
    return int(item.stock_qty) + min(
        int(item.buy_qty), int(item.jita_sell_volume)
    )


def preferred_completable(
    line: FittingBuyOrderLine,
    order: FittingBuyOrder,
    preferred_type_id: int,
) -> int | None:
    """How many hulls on this line can use the preferred module.

    None means depth is unknown — caller should not split.
    """
    # Use unswapped BOM so we measure preferred availability, not substitutes.
    boms = line_type_quantities(
        [line],
        include_hull=order.include_hull,
        apply_line_swaps=False,
    )
    if not boms:
        return None
    per = int(boms[0].per_ship.get(preferred_type_id, 0) or 0)
    if per <= 0:
        return None
    item = order.items.filter(eve_type_id=preferred_type_id).first()
    available = _available_modules(item)
    if available is None:
        return None
    return min(int(line.quantity), available // per)


def apply_swap_on_line(
    line: FittingBuyOrderLine,
    *,
    preferred_type_id: int,
    substitute_type_id: int,
    notes: str = "",
    swap_hull_qty: int | None = None,
) -> bool:
    """Record a preferred→substitute swap on one line. Returns True if saved."""
    if preferred_type_id == substitute_type_id:
        return False
    swaps = [
        swap
        for swap in (line.swaps or [])
        if int(swap.get("preferred_type_id") or 0) != preferred_type_id
    ]
    swaps.append(
        {
            "preferred_type_id": preferred_type_id,
            "substitute_type_id": substitute_type_id,
            "notes": notes or "",
        }
    )
    line.swaps = swaps
    fields = ["swaps"]
    if swap_hull_qty is not None:
        line.swap_hull_qty = max(
            0, min(int(line.quantity), int(swap_hull_qty))
        )
        fields.append("swap_hull_qty")
    elif line.swap_hull_qty is not None:
        # Full-line swap — clear any prior partial split.
        line.swap_hull_qty = None
        fields.append("swap_hull_qty")
    line.save(update_fields=fields)
    return True


def apply_swap_on_line_split(
    line: FittingBuyOrderLine,
    order: FittingBuyOrder,
    *,
    preferred_type_id: int,
    substitute_type_id: int,
    notes: str = "",
) -> int:
    """
    Apply a swap, recording a partial hull split when only part of the qty is short.

    Returns 1 if the line was updated, else 0.
    """
    if preferred_type_id == substitute_type_id:
        return 0

    completable = preferred_completable(line, order, preferred_type_id)
    swap_hull_qty: int | None = None
    if completable is not None and 0 < completable < int(line.quantity):
        swap_hull_qty = int(line.quantity) - completable

    if apply_swap_on_line(
        line,
        preferred_type_id=preferred_type_id,
        substitute_type_id=substitute_type_id,
        notes=notes,
        swap_hull_qty=swap_hull_qty,
    ):
        return 1
    return 0


def apply_swap_on_order(
    order: FittingBuyOrder,
    *,
    preferred_type_id: int,
    substitute_type_id: int,
    notes: str = "",
) -> int:
    """
    Apply preferred→substitute on every line whose current BOM still needs preferred.

    Partially completable lines keep original hulls and set swap_hull_qty for the rest.
    Returns number of lines updated.
    """
    if preferred_type_id == substitute_type_id:
        return 0

    updated = 0
    lines = list(
        order.lines.select_related("fitting").order_by("sort_order", "id")
    )
    for line in lines:
        effective = line_type_quantities(
            [line], include_hull=order.include_hull
        )
        if not effective or preferred_type_id not in effective[0].total:
            continue
        touched = apply_swap_on_line_split(
            line,
            order,
            preferred_type_id=preferred_type_id,
            substitute_type_id=substitute_type_id,
            notes=notes,
        )
        if touched:
            updated += 1

    if updated:
        sync_order_items(order)
    return updated
