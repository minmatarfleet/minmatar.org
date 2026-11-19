"""Provisional industry orders: a claiming window, then only claimed work starts."""

from __future__ import annotations

import logging
from datetime import datetime, time
from datetime import timezone as dt_timezone

from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from groups.helpers.feature_access import can_use_feature
from industry.models import (
    IndustryOrder,
    IndustryOrderItem,
    IndustryOrderItemAssignment,
    IndustryOrderUnfulfilledItem,
)

logger = logging.getLogger(__name__)

ORDER_MANAGE_FEATURE = "industry.order.manage"


def order_is_provisional(order: IndustryOrder) -> bool:
    """True while pilots may claim and building has not started."""
    return (
        order.starts_at is not None
        and order.started_at is None
        and order.fulfilled_at is None
    )


def format_eve_datetime(value: datetime) -> str:
    """UTC clock label for notifications (EVE time)."""
    stamp = value
    if timezone.is_naive(stamp):
        stamp = timezone.make_aware(stamp, dt_timezone.utc)
    return stamp.astimezone(dt_timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def claiming_hours(starts_at: datetime | None, *, now=None) -> int | None:
    """Whole hours from now until the order starts, at least 1 when still ahead."""
    if starts_at is None:
        return None
    moment = now or timezone.now()
    seconds = (starts_at - moment).total_seconds()
    if seconds <= 0:
        return 0
    return max(1, round(seconds / 3600))


def validate_starts_at(starts_at: datetime | None, needed_by) -> str | None:
    """
    Return an error detail when a provisional start time is unusable.

    ``None`` means the order opens immediately.
    """
    if starts_at is None:
        return None
    stamp = starts_at
    if timezone.is_naive(stamp):
        stamp = timezone.make_aware(stamp, dt_timezone.utc)
    if stamp <= timezone.now():
        return "Start time must be in the future."
    deadline = timezone.make_aware(
        datetime.combine(needed_by, time.max), dt_timezone.utc
    )
    if stamp > deadline:
        return "Start time must be on or before the needed-by date."
    return None


def user_can_import_unfulfilled(user) -> bool:
    return can_use_feature(user, ORDER_MANAGE_FEATURE)


def mark_imported_unfulfilled(
    source_order_id: int, new_order: IndustryOrder, type_ids: list[int]
) -> int:
    """Point still-open remainders of these types at the order that took them."""
    if not type_ids:
        return 0
    return IndustryOrderUnfulfilledItem.objects.filter(
        order_id=source_order_id,
        imported_into__isnull=True,
        eve_type_id__in=type_ids,
    ).update(imported_into=new_order)


def drop_unclaimed_quantities(
    order: IndustryOrder,
) -> list[IndustryOrderUnfulfilledItem]:
    """
    Shrink each line to its claimed quantity and record the rest as unfulfilled.

    A line nobody claimed is removed. Safe to run once per order: a second pass
    sees claimed == quantity and writes nothing.
    """
    created: list[IndustryOrderUnfulfilledItem] = []
    items = list(
        IndustryOrderItem.objects.select_for_update()
        .filter(order=order)
        .select_related("eve_type")
    )
    for item in items:
        claimed = (
            IndustryOrderItemAssignment.objects.filter(
                order_item=item
            ).aggregate(total=Sum("quantity"))["total"]
            or 0
        )
        claimed = min(claimed, item.quantity)
        unclaimed = item.quantity - claimed
        if unclaimed > 0:
            created.append(
                IndustryOrderUnfulfilledItem.objects.create(
                    order=order,
                    eve_type=item.eve_type,
                    quantity=unclaimed,
                )
            )
        if claimed <= 0:
            item.delete()
        elif claimed != item.quantity:
            item.quantity = claimed
            item.save(update_fields=["quantity"])
    return created


def _due_orders():
    now = timezone.now()
    return IndustryOrder.objects.filter(
        Q(
            starts_at__isnull=False,
            starts_at__lte=now,
            started_at__isnull=True,
            fulfilled_at__isnull=True,
        )
        | Q(
            starts_at__isnull=False,
            started_at__isnull=False,
            selection_notified_at__isnull=True,
            fulfilled_at__isnull=True,
        )
    )


def start_provisional_order(order_id: int) -> bool:
    """
    Close one due claiming period and tell selected builders to start.

    Returns True when this call closed the period or sent the start notice.
    """
    # pylint: disable=import-outside-toplevel
    from app.celery import app
    from industry.helpers.notifications import emit_order_selected

    should_notify = False
    dropped = False
    with transaction.atomic():
        order = (
            IndustryOrder.objects.select_for_update()
            .filter(pk=order_id)
            .first()
        )
        if (
            order is None
            or order.starts_at is None
            or order.fulfilled_at is not None
        ):
            return False
        now = timezone.now()
        if order.started_at is None:
            if order.starts_at > now:
                return False
            drop_unclaimed_quantities(order)
            order.started_at = now
            order.save(update_fields=["started_at"])
            dropped = True
        if order.selection_notified_at is None:
            should_notify = True

    if dropped:
        if IndustryOrderItem.objects.filter(order_id=order_id).exists():
            try:
                app.signature(
                    "industry.tasks.compute_order_profit_breakdown_task",
                    args=[order_id],
                ).delay()
            except Exception:
                logger.exception(
                    "Failed to enqueue profit breakdown after starting order %s",
                    order_id,
                )

    if not should_notify:
        return dropped

    order = IndustryOrder.objects.select_related("location").get(pk=order_id)
    try:
        emit_order_selected(order)
    except Exception:
        logger.exception(
            "Failed to notify selected builders for order %s", order_id
        )
        return dropped

    IndustryOrder.objects.filter(
        pk=order_id, selection_notified_at__isnull=True
    ).update(selection_notified_at=timezone.now())
    return True


def start_due_provisional_orders() -> int:
    """Start every provisional order whose claiming period has ended."""
    started = 0
    order_ids = list(_due_orders().values_list("pk", flat=True))
    for order_id in order_ids:
        try:
            if start_provisional_order(order_id):
                started += 1
        except Exception:
            logger.exception("Failed to start provisional order %s", order_id)
    return started
