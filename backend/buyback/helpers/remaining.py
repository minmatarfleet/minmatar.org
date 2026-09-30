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


def _qty_by_type(
    reason: str,
    *,
    after=None,
) -> dict[int, int]:
    qs = BuybackLedgerEntry.objects.filter(reason=reason)
    if after is not None:
        qs = qs.filter(occurred_at__gt=after)
    rows = qs.values("eve_type_id").annotate(total=Sum("quantity"))
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
    """Listed stock. With a hangar snapshot this matches what Match stock sells."""
    if hangar_snapshot_quantities() is not None:
        return remaining_sale_quantities(exclude_order_id=exclude_order_id)
    pending = pending_purchase_quantities(exclude_order_id=exclude_order_id)
    fallback: dict[int, int] = {}
    for type_id, qty in BuybackAcceptedItem.objects.filter(
        active=True
    ).values_list("eve_type_id", "stockpile_quantity"):
        fallback[int(type_id)] = int(qty or 0)
    return _subtract_pending(fallback, pending)


def _ledger_net_quantities(
    *,
    exclude_order_id: int | None = None,
) -> dict[int, int]:
    """Inbound contracts minus outbound contracts minus pending. Ignores market sales."""
    inbound = _qty_by_type(BuybackLedgerEntry.Reason.IN_CONTRACT)
    outbound = _qty_by_type(BuybackLedgerEntry.Reason.SOLD_CONTRACT)
    pending = pending_purchase_quantities(exclude_order_id=exclude_order_id)
    remaining: dict[int, int] = {}
    for type_id in set(inbound) | set(outbound) | set(pending):
        qty = (
            inbound.get(type_id, 0)
            - outbound.get(type_id, 0)
            - pending.get(type_id, 0)
        )
        if qty > 0:
            remaining[type_id] = qty
    return remaining


def remaining_sale_quantities(
    *,
    exclude_order_id: int | None = None,
) -> dict[int, int]:
    """
    On-hand for sale.

    Without a hangar snapshot: inbound contracts minus outbound contracts
    minus pending purchase reservations. Market sales are not in that ledger.

    With a snapshot: the physical hangar is what the stock page lists. Sales
    recorded after that snapshot (contracts and market orders) are subtracted
    so a stale scan cannot be sold twice, then pending reservations are held
    back. Contract receipts are not added on top of the scan — the next
    snapshot picks those up, and adding them early double-counts ore the
    scan already includes.
    """
    snapshot_row = BuybackHangarSnapshot.objects.order_by("-taken_at").first()
    if snapshot_row is None:
        return _ledger_net_quantities(exclude_order_id=exclude_order_id)

    snapshot = hangar_snapshot_quantities() or {}
    taken_at = snapshot_row.taken_at
    sold_contract_after = _qty_by_type(
        BuybackLedgerEntry.Reason.SOLD_CONTRACT,
        after=taken_at,
    )
    sold_order_after = _qty_by_type(
        BuybackLedgerEntry.Reason.SOLD_ORDER,
        after=taken_at,
    )
    pending = pending_purchase_quantities(exclude_order_id=exclude_order_id)
    type_ids = (
        set(snapshot)
        | set(sold_contract_after)
        | set(sold_order_after)
        | set(pending)
    )
    remaining: dict[int, int] = {}
    for type_id in type_ids:
        qty = (
            snapshot.get(type_id, 0)
            - sold_contract_after.get(type_id, 0)
            - sold_order_after.get(type_id, 0)
            - pending.get(type_id, 0)
        )
        if qty > 0:
            remaining[type_id] = qty
    return remaining
