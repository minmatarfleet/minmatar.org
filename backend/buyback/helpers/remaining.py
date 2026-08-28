"""Remaining buyback stock from inbound minus outbound contracts."""

from __future__ import annotations

from django.db.models import Sum

from buyback.models import (
    BuybackAcceptedItem,
    BuybackHangarSnapshot,
    BuybackLedgerEntry,
    BuybackPurchaseOrder,
    BuybackPurchaseOrderLine,
)


def _qty_by_type(reason: str) -> dict[int, int]:
    rows = (
        BuybackLedgerEntry.objects.filter(reason=reason)
        .values("eve_type_id")
        .annotate(total=Sum("quantity"))
    )
    return {
        int(row["eve_type_id"]): int(row["total"] or 0)
        for row in rows
        if int(row["total"] or 0) > 0
    }


def pending_purchase_quantities(
    *,
    exclude_order_id: int | None = None,
) -> dict[int, int]:
    """Quantities held by pending purchase orders."""
    qs = BuybackPurchaseOrderLine.objects.filter(
        order__status=BuybackPurchaseOrder.Status.PENDING,
    )
    if exclude_order_id is not None:
        qs = qs.exclude(order_id=exclude_order_id)
    rows = qs.values("eve_type_id").annotate(total=Sum("quantity"))
    return {
        int(row["eve_type_id"]): int(row["total"] or 0)
        for row in rows
        if int(row["total"] or 0) > 0
    }


def hangar_snapshot_quantities() -> dict[int, int] | None:
    """Latest hangar snapshot, or None if none has been taken."""
    snapshot = BuybackHangarSnapshot.objects.order_by("-taken_at").first()
    if snapshot is None:
        return None
    quantities: dict[int, int] = {}
    for key, qty in (snapshot.quantities or {}).items():
        try:
            parsed = int(qty)
        except (TypeError, ValueError):
            continue
        quantities[int(key)] = parsed
    return quantities


def _subtract_pending(
    quantities: dict[int, int],
    pending: dict[int, int],
) -> dict[int, int]:
    remaining: dict[int, int] = {}
    for type_id, qty in quantities.items():
        left = int(qty) - pending.get(type_id, 0)
        if left > 0:
            remaining[type_id] = left
    return remaining


def available_stock_quantities(
    *,
    exclude_order_id: int | None = None,
) -> dict[int, int]:
    """Hangar (or stockpile fallback) minus pending purchase reservations."""
    pending = pending_purchase_quantities(exclude_order_id=exclude_order_id)
    snapshot = hangar_snapshot_quantities()
    if snapshot is not None:
        return _subtract_pending(snapshot, pending)
    fallback: dict[int, int] = {}
    for type_id, qty in BuybackAcceptedItem.objects.filter(
        active=True
    ).values_list("eve_type_id", "stockpile_quantity"):
        fallback[int(type_id)] = int(qty or 0)
    return _subtract_pending(fallback, pending)


def remaining_sale_quantities(
    *,
    exclude_order_id: int | None = None,
) -> dict[int, int]:
    """
    On-hand for sale: inbound contracts minus outbound contracts minus pending.

    When a hangar snapshot exists, also cap to hangar minus pending so a
    reserved purchase cannot be sold again from listed stock.
    """
    inbound = _qty_by_type(BuybackLedgerEntry.Reason.IN_CONTRACT)
    outbound = _qty_by_type(BuybackLedgerEntry.Reason.SOLD_CONTRACT)
    pending = pending_purchase_quantities(exclude_order_id=exclude_order_id)
    snapshot = hangar_snapshot_quantities()
    type_ids = set(inbound) | set(outbound) | set(pending)
    remaining: dict[int, int] = {}
    for type_id in type_ids:
        qty = (
            inbound.get(type_id, 0)
            - outbound.get(type_id, 0)
            - pending.get(type_id, 0)
        )
        if snapshot is not None:
            hangar_left = snapshot.get(type_id, 0) - pending.get(type_id, 0)
            qty = min(qty, hangar_left)
        if qty > 0:
            remaining[type_id] = qty
    return remaining
