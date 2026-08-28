"""Create and settle buyback purchase orders."""

from __future__ import annotations

from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone
from eveonline.helpers.characters import user_primary_character
from eveonline.models import EveCharacter
from eveuniverse.models import EveType

from buyback.discord_tasks import (
    notify_buyback_purchase_created_task,
    notify_buyback_purchase_status_changed_task,
)
from buyback.helpers.purchase_discord import discord_thread_url
from buyback.helpers.purchase_fill import PurchaseFill, fill_purchase
from buyback.helpers.remaining import remaining_sale_quantities
from buyback.models import (
    BuybackLedgerEntry,
    BuybackPurchaseOrder,
    BuybackPurchaseOrderLine,
    EveBuybackSettings,
)


class PurchaseOrderError(Exception):
    """Buyer-facing purchase order failure."""


def _lock_hangar_sales() -> None:
    """Serialize hangar sales so concurrent places cannot oversell."""
    settings = EveBuybackSettings.load()
    EveBuybackSettings.objects.select_for_update().get(pk=settings.pk)
    list(
        BuybackPurchaseOrder.objects.select_for_update()
        .filter(status=BuybackPurchaseOrder.Status.PENDING)
        .order_by("pk")
    )


def serialize_fill(fill: PurchaseFill) -> dict:
    return {
        "picks": [
            {
                "type_id": pick.type_id,
                "name": pick.name,
                "quantity": pick.quantity,
                "fill_source": pick.fill_source,
                "unit_price": pick.unit_price,
                "line_total": pick.line_total,
            }
            for pick in fill.picks
        ],
        "shortfalls": [
            {
                "type_id": row.type_id,
                "name": row.name,
                "quantity": row.quantity,
            }
            for row in fill.shortfalls
        ],
        "unresolved_names": fill.unresolved_names,
        "janice_tsv": fill.janice_tsv,
        "shortfall_tsv": fill.shortfall_tsv,
        "contract_total": fill.contract_total,
        "refine_rate": fill.refine_rate,
        "refine_rate_source": fill.refine_rate_source,
        "facility_key": fill.facility_key,
        "facility_name": fill.facility_name,
        "sell_price_basis": fill.sell_price_basis,
        "sell_markup": fill.sell_markup,
    }


def janice_tsv_for_order(order: BuybackPurchaseOrder) -> str:
    return "\r\n".join(
        f"{line.name}\t{line.quantity}" for line in order.lines.all()
    )


def serialize_order(order: BuybackPurchaseOrder) -> dict:
    lines = list(order.lines.all())
    return {
        "id": order.pk,
        "status": order.status,
        "source": order.source,
        "created_by_user_id": order.created_by_id,
        "character_id": order.character_id,
        "character_name": order.character_name,
        "contract_total": order.contract_total,
        "sell_price_basis": order.sell_price_basis,
        "sell_markup": float(order.sell_markup),
        "janice_tsv": janice_tsv_for_order(order),
        "created_at": order.created_at.isoformat(),
        "completed_at": (
            order.completed_at.isoformat() if order.completed_at else None
        ),
        "discord_thread_id": order.discord_thread_id,
        "discord_thread_url": discord_thread_url(order.discord_thread_id),
        "lines": [
            {
                "type_id": line.eve_type_id,
                "name": line.name,
                "quantity": line.quantity,
                "unit_price": float(line.unit_price),
                "line_total": float(line.line_total),
                "fill_source": line.fill_source,
            }
            for line in lines
        ],
    }


def _sold_by_type_since(character_id: int, since) -> dict[int, int]:
    rows = (
        BuybackLedgerEntry.objects.filter(
            reason=BuybackLedgerEntry.Reason.SOLD_CONTRACT,
            counterparty_id=character_id,
            occurred_at__gte=since,
        )
        .values("eve_type_id")
        .annotate(total=Sum("quantity"))
    )
    return {
        int(row["eve_type_id"]): int(row["total"] or 0)
        for row in rows
        if int(row["total"] or 0) > 0
    }


def _allocate_order_lines(
    order: BuybackPurchaseOrder,
    allocated: dict[tuple[int, int], int],
) -> None:
    if not order.character_id:
        return
    for line in order.lines.all():
        key = (order.character_id, line.eve_type_id)
        allocated[key] = allocated.get(key, 0) + int(line.quantity)


def _allocated_before_order(
    order: BuybackPurchaseOrder,
) -> dict[tuple[int, int], int]:
    allocated: dict[tuple[int, int], int] = {}
    if not order.character_id:
        return allocated
    earlier = (
        BuybackPurchaseOrder.objects.filter(
            status=BuybackPurchaseOrder.Status.PENDING,
            character_id=order.character_id,
        )
        .filter(
            Q(created_at__lt=order.created_at)
            | Q(created_at=order.created_at, pk__lt=order.pk)
        )
        .prefetch_related("lines")
        .order_by("created_at", "pk")
    )
    for earlier_order in earlier:
        _allocate_order_lines(earlier_order, allocated)
    return allocated


def _outbound_available_for_order(
    order: BuybackPurchaseOrder,
    allocated: dict[tuple[int, int], int],
) -> bool:
    if not order.character_id:
        return False
    sold = _sold_by_type_since(order.character_id, order.created_at)
    for line in order.lines.all():
        key = (order.character_id, line.eve_type_id)
        available = sold.get(line.eve_type_id, 0) - allocated.get(key, 0)
        if available < line.quantity:
            return False
    return True


def _order_character(order_character: EveCharacter | None, user):
    if order_character is not None:
        return order_character.character_id, order_character.character_name
    primary = user_primary_character(user)
    if primary is None:
        return None, ""
    return primary.character_id, primary.character_name


@transaction.atomic
def create_purchase_order(
    *,
    user,
    paste: str,
    source: str,
    character: EveCharacter | None = None,
    facility_key: str | None = None,
    use_reprocessing_implants: bool = False,
) -> BuybackPurchaseOrder:
    """Place a pending purchase from the current fill, or raise."""
    source = (source or BuybackPurchaseOrder.Source.STOCKPILE).strip().lower()
    if source not in (
        BuybackPurchaseOrder.Source.PLANNER,
        BuybackPurchaseOrder.Source.STOCKPILE,
    ):
        raise PurchaseOrderError("source must be planner or stockpile")

    _lock_hangar_sales()
    settings = EveBuybackSettings.load()
    fill = fill_purchase(
        paste,
        settings=settings,
        character=character,
        facility_key=facility_key,
        use_reprocessing_implants=use_reprocessing_implants,
    )
    if not fill.picks:
        raise PurchaseOrderError("Buyback has nothing that matches that list.")
    if any(pick.unit_price is None for pick in fill.picks):
        raise PurchaseOrderError(
            "Could not price every hangar line. Try again later."
        )
    if fill.contract_total <= 0:
        raise PurchaseOrderError("Contract total must be positive.")

    remaining = remaining_sale_quantities()
    for pick in fill.picks:
        if remaining.get(pick.type_id, 0) < pick.quantity:
            raise PurchaseOrderError(
                "That stock is no longer available. Refresh and try again."
            )

    character_id, character_name = _order_character(character, user)
    order = BuybackPurchaseOrder.objects.create(
        status=BuybackPurchaseOrder.Status.PENDING,
        source=source,
        created_by=user,
        character_id=character_id,
        character_name=character_name,
        paste=paste,
        contract_total=fill.contract_total,
        sell_price_basis=fill.sell_price_basis,
        sell_markup=fill.sell_markup,
    )
    type_ids = [pick.type_id for pick in fill.picks]
    types = {
        eve_type.id: eve_type
        for eve_type in EveType.objects.filter(id__in=type_ids)
    }
    missing = [type_id for type_id in type_ids if type_id not in types]
    if missing:
        raise PurchaseOrderError(
            "Could not resolve item types. Try again later."
        )
    BuybackPurchaseOrderLine.objects.bulk_create(
        [
            BuybackPurchaseOrderLine(
                order=order,
                eve_type=types[pick.type_id],
                name=pick.name,
                quantity=pick.quantity,
                unit_price=pick.unit_price,
                line_total=pick.line_total,
                fill_source=pick.fill_source,
            )
            for pick in fill.picks
        ]
    )
    notify_buyback_purchase_created_task.delay(order.pk)
    return order


@transaction.atomic
def complete_purchase_order(order: BuybackPurchaseOrder, user) -> None:
    order = (
        BuybackPurchaseOrder.objects.select_for_update()
        .prefetch_related("lines")
        .get(pk=order.pk)
    )
    if order.status != BuybackPurchaseOrder.Status.PENDING:
        raise PurchaseOrderError("Only pending orders can be completed.")
    allocated = _allocated_before_order(order)
    if not _outbound_available_for_order(order, allocated):
        raise PurchaseOrderError(
            "No matching outbound contract has synced for this order yet."
        )
    order.status = BuybackPurchaseOrder.Status.COMPLETED
    order.completed_at = timezone.now()
    order.completed_by = user
    order.save(
        update_fields=[
            "status",
            "completed_at",
            "completed_by",
            "updated_at",
        ]
    )
    notify_buyback_purchase_status_changed_task.delay(order.pk)


@transaction.atomic
def cancel_purchase_order(order: BuybackPurchaseOrder) -> None:
    order = BuybackPurchaseOrder.objects.select_for_update().get(pk=order.pk)
    if order.status != BuybackPurchaseOrder.Status.PENDING:
        raise PurchaseOrderError("Only pending orders can be cancelled.")
    order.status = BuybackPurchaseOrder.Status.CANCELLED
    order.completed_at = timezone.now()
    order.save(update_fields=["status", "completed_at", "updated_at"])
    notify_buyback_purchase_status_changed_task.delay(order.pk)


def discord_ack_order(
    order: BuybackPurchaseOrder, *, action: str, actor
) -> BuybackPurchaseOrder:
    action = (action or "").strip().lower()
    if action == "complete":
        complete_purchase_order(order, actor)
    elif action == "cancel":
        cancel_purchase_order(order)
    else:
        raise PurchaseOrderError("Unknown Discord ack action.")
    order.refresh_from_db()
    return order


@transaction.atomic
def try_complete_from_outbound_contracts() -> int:
    """Complete pending orders covered by synced outbound sale contracts."""
    completed = 0
    allocated: dict[tuple[int, int], int] = {}
    pending = (
        BuybackPurchaseOrder.objects.filter(
            status=BuybackPurchaseOrder.Status.PENDING,
            character_id__isnull=False,
        )
        .prefetch_related("lines")
        .order_by("created_at", "pk")
    )
    for order in pending:
        if not _outbound_available_for_order(order, allocated):
            continue
        order.status = BuybackPurchaseOrder.Status.COMPLETED
        order.completed_at = timezone.now()
        order.save(update_fields=["status", "completed_at", "updated_at"])
        notify_buyback_purchase_status_changed_task.delay(order.pk)
        _allocate_order_lines(order, allocated)
        completed += 1
    return completed
