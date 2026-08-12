"""Shopping allocations: split a short item's buy qty across variants."""

from __future__ import annotations

from decimal import Decimal

from eveuniverse.models import EveType

from market.helpers.fitting_buy_alternates import (
    listed_substitutes_by_preferred,
    parse_jita_sell_min,
    shopping_alternate_types_for,
)
from market.models.fitting_buy_order import (
    FittingBuyOrder,
    FittingBuyOrderItem,
)

ALTERNATE_LIMIT = 20


class AllocationError(ValueError):
    """Invalid shopping allocation payload."""


def cached_jita_volume(
    order: FittingBuyOrder,
    type_id: int,
    *,
    items_by_id: dict[int, FittingBuyOrderItem] | None = None,
) -> int | None:
    """Jita sell volume from the BOM item row or variant cache."""
    item = None
    if items_by_id is not None:
        item = items_by_id.get(type_id)
    else:
        item = FittingBuyOrderItem.objects.filter(
            order=order, eve_type_id=type_id
        ).first()
    if item is not None and item.jita_sell_volume is not None:
        return int(item.jita_sell_volume)
    raw = (order.variant_jita_cache or {}).get(str(type_id))
    if not raw:
        return None
    volume = raw.get("volume")
    if volume is None:
        return None
    return int(volume)


def cached_jita_depth(
    order: FittingBuyOrder,
    type_id: int,
    *,
    items_by_id: dict[int, FittingBuyOrderItem] | None = None,
) -> dict:
    item = None
    if items_by_id is not None:
        item = items_by_id.get(type_id)
    else:
        item = FittingBuyOrderItem.objects.filter(
            order=order, eve_type_id=type_id
        ).first()
    if item is not None and item.jita_sell_volume is not None:
        return {
            "jita_sell_volume": int(item.jita_sell_volume),
            "jita_order_count": item.jita_order_count,
            "jita_sell_min": (
                str(item.jita_sell_min)
                if item.jita_sell_min is not None
                else None
            ),
        }
    raw = (order.variant_jita_cache or {}).get(str(type_id)) or {}
    sell_min = raw.get("sell_min")
    volume = raw.get("volume")
    order_count = raw.get("order_count")
    return {
        "jita_sell_volume": int(volume) if volume is not None else None,
        "jita_order_count": (
            int(order_count) if order_count is not None else None
        ),
        "jita_sell_min": str(sell_min) if sell_min is not None else None,
    }


def cached_jita_sell_mins(
    order: FittingBuyOrder,
    *,
    items_by_id: dict[int, FittingBuyOrderItem] | None = None,
) -> dict[int, Decimal]:
    """Jita sell mins from BOM item rows, then variant cache."""
    result: dict[int, Decimal] = {}
    rows = (
        items_by_id.values() if items_by_id is not None else order.items.all()
    )
    for row in rows:
        parsed = parse_jita_sell_min(row.jita_sell_min)
        if parsed is not None:
            result[row.eve_type_id] = parsed
    for key, raw in (order.variant_jita_cache or {}).items():
        try:
            type_id = int(key)
        except (TypeError, ValueError):
            continue
        if type_id in result:
            continue
        parsed = parse_jita_sell_min((raw or {}).get("sell_min"))
        if parsed is not None:
            result[type_id] = parsed
    return result


def allowed_allocation_type_ids(
    preferred: EveType,
    *,
    listed_substitute_ids: set[int] | None = None,
    jita_sell_min_by_type: (
        dict[int, Decimal | float | str | None] | None
    ) = None,
) -> set[int]:
    allowed = {preferred.id}
    allowed.update(
        alt.id
        for alt in shopping_alternate_types_for(
            preferred,
            limit=ALTERNATE_LIMIT,
            listed_substitute_ids=listed_substitute_ids,
            jita_sell_min_by_type=jita_sell_min_by_type,
        )
    )
    return allowed


def normalize_entries(entries: list[dict]) -> list[dict]:
    merged: dict[int, int] = {}
    for entry in entries:
        type_id = int(entry.get("type_id") or 0)
        qty = int(entry.get("qty") or 0)
        if type_id <= 0:
            raise AllocationError("Each allocation needs a type_id.")
        if qty < 0:
            raise AllocationError("Allocation qty cannot be negative.")
        merged[type_id] = merged.get(type_id, 0) + qty
    return [
        {"type_id": type_id, "qty": qty}
        for type_id, qty in merged.items()
        if qty > 0
    ]


def effective_buy_map(order: FittingBuyOrder, plan) -> dict[int, int]:
    """plan.buy with shopping_allocations applied.

    Variant qtys come from the split; any remainder stays on the preferred type.
    """
    buy = {tid: qty for tid, qty in plan.buy.items() if qty > 0}
    allocations = order.shopping_allocations or {}
    for preferred_key, raw_entries in allocations.items():
        preferred_id = int(preferred_key)
        original = buy.get(preferred_id, 0)
        if original <= 0:
            continue
        try:
            entries = normalize_entries(raw_entries or [])
        except AllocationError:
            continue
        if not entries:
            continue
        variant_total = sum(
            entry["qty"]
            for entry in entries
            if entry["type_id"] != preferred_id
        )
        if variant_total > original:
            continue
        buy.pop(preferred_id, None)
        for entry in entries:
            tid = entry["type_id"]
            if tid == preferred_id:
                continue
            buy[tid] = buy.get(tid, 0) + entry["qty"]
        preferred_qty = original - variant_total
        if preferred_qty > 0:
            buy[preferred_id] = preferred_qty
    return buy


def prune_invalid_allocations(order: FittingBuyOrder, plan) -> bool:
    """Drop allocations that no longer match BOM buy qty. Returns True if saved."""
    allocations = dict(order.shopping_allocations or {})
    if not allocations:
        return False
    changed = False
    for key in list(allocations):
        preferred_id = int(key)
        buy_qty = plan.buy.get(preferred_id, 0)
        if buy_qty <= 0:
            allocations.pop(key, None)
            changed = True
            continue
        try:
            entries = normalize_entries(allocations.get(key) or [])
        except AllocationError:
            allocations.pop(key, None)
            changed = True
            continue
        total = sum(entry["qty"] for entry in entries)
        if not entries or total > buy_qty:
            allocations.pop(key, None)
            changed = True
    if changed:
        order.shopping_allocations = allocations
        order.save(update_fields=["shopping_allocations", "updated_at"])
    return changed


def set_allocations(
    order: FittingBuyOrder,
    *,
    preferred_type_id: int,
    entries: list[dict],
) -> None:
    """
    Replace allocations for one preferred type.

    Empty entries clears the split (Multibuy goes back to all-preferred).
    Non-empty entries may total less than buy_qty; remainder stays preferred.
    Sum after Jita clamps cannot exceed buy_qty.
    """
    item = (
        FittingBuyOrderItem.objects.filter(
            order=order, eve_type_id=preferred_type_id
        )
        .select_related("eve_type")
        .first()
    )
    if item is None or item.buy_qty <= 0:
        raise AllocationError("That module is not on this purchase list.")

    allocations = dict(order.shopping_allocations or {})
    key = str(preferred_type_id)
    normalized = normalize_entries(entries)
    if not normalized:
        if key in allocations:
            allocations.pop(key, None)
            order.shopping_allocations = allocations
            order.save(update_fields=["shopping_allocations", "updated_at"])
        return

    fitting_ids = order.lines.values_list("fitting_id", flat=True)
    listed = listed_substitutes_by_preferred(fitting_ids).get(
        preferred_type_id, set()
    )
    items_by_id = {row.eve_type_id: row for row in order.items.all()}
    allowed = allowed_allocation_type_ids(
        item.eve_type,
        listed_substitute_ids=listed,
        jita_sell_min_by_type=cached_jita_sell_mins(
            order, items_by_id=items_by_id
        ),
    )
    clamped: list[dict] = []
    for entry in normalized:
        type_id = entry["type_id"]
        qty = entry["qty"]
        if type_id not in allowed:
            raise AllocationError(
                "That type is not a matching variant of the short module."
            )
        volume = cached_jita_volume(order, type_id, items_by_id=items_by_id)
        if volume is not None and qty > volume:
            qty = volume
        if qty > 0:
            clamped.append({"type_id": type_id, "qty": qty})

    if not clamped:
        if key in allocations:
            allocations.pop(key, None)
            order.shopping_allocations = allocations
            order.save(update_fields=["shopping_allocations", "updated_at"])
        return

    total = sum(entry["qty"] for entry in clamped)
    if total > item.buy_qty:
        raise AllocationError(
            f"Split cannot exceed {item.buy_qty} (got {total} after Jita depth limits)."
        )

    allocations[key] = clamped
    order.shopping_allocations = allocations
    order.save(update_fields=["shopping_allocations", "updated_at"])
