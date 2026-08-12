"""Apply module swaps on fitting buy order lines."""

from __future__ import annotations

from market.helpers.fitting_buy_plan import (
    line_type_quantities,
    sync_order_items,
)
from market.models.fitting_buy_order import (
    FittingBuyOrder,
    FittingBuyOrderLine,
)


def apply_swap_on_line(
    line: FittingBuyOrderLine,
    *,
    preferred_type_id: int,
    substitute_type_id: int,
    notes: str = "",
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
    line.save(update_fields=["swaps"])
    return True


def apply_swap_on_order(
    order: FittingBuyOrder,
    *,
    preferred_type_id: int,
    substitute_type_id: int,
    notes: str = "",
) -> int:
    """
    Apply preferred→substitute on every line whose current BOM still needs preferred.
    Returns number of lines updated.
    """
    if preferred_type_id == substitute_type_id:
        return 0

    updated = 0
    lines = list(order.lines.select_related("fitting"))
    for line in lines:
        boms = line_type_quantities([line], include_hull=order.include_hull)
        if not boms or preferred_type_id not in boms[0].total:
            continue
        if apply_swap_on_line(
            line,
            preferred_type_id=preferred_type_id,
            substitute_type_id=substitute_type_id,
            notes=notes,
        ):
            updated += 1

    if updated:
        sync_order_items(order)
    return updated
