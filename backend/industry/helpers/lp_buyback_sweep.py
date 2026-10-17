"""Hourly LP buyback housekeeping: thread mirror, reminders, auto-cancel."""

from __future__ import annotations

import logging
from datetime import timedelta

from django.utils import timezone

from industry.helpers.lp_buyback_discord import (
    active_lp_buyback_thread_ids,
    close_lp_buyback_thread_id,
    lp_buyback_channel_id,
    notify_order_created,
    post_stalled_reminder,
    stalled_cancel_reason,
)
from industry.helpers.lp_market_orders import (
    ACTIVE_STATUSES,
    AUTO_CANCEL_STATUSES,
    STALLABLE_STATUSES,
    auto_cancel_stalled_order,
)
from industry.models import IndustryLoyaltyPointMarketOrder

logger = logging.getLogger(__name__)

REMIND_AFTER = timedelta(hours=24)
AUTO_CANCEL_AFTER = timedelta(hours=48)
# Pilots always get a full day's warning, even for orders already stalled
# past 48h when this sweep first ran.
MIN_WARNING_BEFORE_CANCEL = AUTO_CANCEL_AFTER - REMIND_AFTER
# Leave the create task time to run before treating a thread as missing.
MISSING_THREAD_GRACE = timedelta(minutes=10)

_TERMINAL_STATUSES = (
    IndustryLoyaltyPointMarketOrder.Status.CANCELLED,
    IndustryLoyaltyPointMarketOrder.Status.COMPLETED,
)


def _orders():
    return IndustryLoyaltyPointMarketOrder.objects.select_related(
        "loyalty_point", "created_by", "claimed_by"
    ).prefetch_related("claims__claimed_by")


def create_missing_threads(now) -> int:
    """Retry thread creation for active orders whose create task failed."""
    created = 0
    missing = _orders().filter(
        status__in=ACTIVE_STATUSES,
        discord_thread_id__isnull=True,
        created_at__lte=now - MISSING_THREAD_GRACE,
    )
    for order in missing:
        notify_order_created(order)
        order.refresh_from_db(fields=["discord_thread_id"])
        if order.discord_thread_id:
            created += 1
            logger.info(
                "Created missing LP buyback thread for order %s", order.pk
            )
    return created


def close_stray_threads() -> int:
    """Archive forum threads still open for completed/cancelled orders."""
    active_ids = active_lp_buyback_thread_ids()
    if not active_ids:
        return 0
    stray_ids = IndustryLoyaltyPointMarketOrder.objects.filter(
        discord_thread_id__in=active_ids,
        status__in=_TERMINAL_STATUSES,
    ).values_list("discord_thread_id", flat=True)
    closed = 0
    for thread_id in stray_ids:
        if close_lp_buyback_thread_id(thread_id):
            closed += 1
    return closed


def auto_cancel_stalled_orders(now) -> int:
    """Cancel pre-LP orders stuck 48h+ whose pilot was warned a day ago."""
    cancelled = 0
    stalled = _orders().filter(
        status__in=AUTO_CANCEL_STATUSES,
        status_changed_at__lte=now - AUTO_CANCEL_AFTER,
        stalled_reminder_at__lte=now - MIN_WARNING_BEFORE_CANCEL,
    )
    for order in stalled:
        if auto_cancel_stalled_order(
            order.pk,
            stalled_before=now - AUTO_CANCEL_AFTER,
            reason=stalled_cancel_reason(order),
        ):
            cancelled += 1
            logger.info("Auto-cancelled stalled LP buyback order %s", order.pk)
    return cancelled


def remind_stalled_orders(now) -> int:
    """Ping whoever owes the next step once the order has waited 24h.

    Pre-LP orders get one reminder before auto-cancel. Awaiting-ISK orders
    are never auto-cancelled (LP already moved), so they are re-pinged daily.
    """
    reminded = 0
    stalled = _orders().filter(
        status__in=STALLABLE_STATUSES,
        status_changed_at__lte=now - REMIND_AFTER,
    )
    for order in stalled:
        auto_cancels = order.status in AUTO_CANCEL_STATUSES
        last = order.stalled_reminder_at
        if last is not None and (auto_cancels or last > now - REMIND_AFTER):
            continue
        # Claim the reminder slot first so overlapping sweeps never double
        # ping; the status match drops orders that moved since the query.
        claimed = IndustryLoyaltyPointMarketOrder.objects.filter(
            pk=order.pk,
            status=order.status,
            stalled_reminder_at=last,
        ).update(stalled_reminder_at=now)
        if not claimed:
            continue
        cancel_at = None
        if auto_cancels:
            cancel_at = max(
                order.status_changed_at + AUTO_CANCEL_AFTER,
                now + MIN_WARNING_BEFORE_CANCEL,
            )
        waited = now - order.status_changed_at
        post_stalled_reminder(
            order,
            waited_hours=int(waited.total_seconds() // 3600),
            cancel_at=cancel_at,
        )
        reminded += 1
    return reminded


def sweep_lp_buyback_orders(now=None) -> dict:
    now = now or timezone.now()
    stats = {
        "threads_created": 0,
        "threads_closed": 0,
        "cancelled": 0,
        "reminded": 0,
    }
    if lp_buyback_channel_id():
        stats["threads_created"] = create_missing_threads(now)
        stats["threads_closed"] = close_stray_threads()
    # Cancel before reminding so one sweep never warns and cancels at once.
    stats["cancelled"] = auto_cancel_stalled_orders(now)
    stats["reminded"] = remind_stalled_orders(now)
    logger.info("LP buyback sweep: %s", stats)
    return stats
