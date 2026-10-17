"""Hourly LP buyback housekeeping: thread mirror, reminders, auto-cancel.

- Open 7+ days with no taker: weekly digest to the Conversion Team channel.
- Poster owes the next pre-LP step: one reminder at 24h, cancel at 48h.
- Claimer owes a step, or ISK is owed: pinged every 24h, never cancelled.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from industry.helpers.lp_buyback_discord import (
    active_lp_buyback_thread_ids,
    close_lp_buyback_thread_id,
    lp_buyback_channel_id,
    lp_conversion_alert_channel_id,
    notify_order_created,
    post_stale_open_orders_digest,
    post_stalled_reminder,
    poster_is_stalling,
    stalled_cancel_reason,
)
from industry.helpers.lp_market_orders import (
    ACTIVE_STATUSES,
    OPEN,
    PRE_LP_STATUSES,
    STALLABLE_STATUSES,
    TERMINAL_STATUSES,
    auto_cancel_stalled_order,
)
from industry.models import IndustryLoyaltyPointMarketOrder

logger = logging.getLogger(__name__)

REMIND_AFTER = timedelta(hours=24)
AUTO_CANCEL_AFTER = timedelta(hours=48)
# Pilots always get a full day's warning, even for orders already stalled
# past 48h when this sweep first ran.
MIN_WARNING_BEFORE_CANCEL = AUTO_CANCEL_AFTER - REMIND_AFTER
STALE_OPEN_AFTER = timedelta(days=7)
# Leave the create task time to run before treating a thread as missing.
MISSING_THREAD_GRACE = timedelta(minutes=10)


def _not_reminded_since(cutoff) -> Q:
    return Q(stalled_reminder_at__isnull=True) | Q(
        stalled_reminder_at__lte=cutoff
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
        status__in=TERMINAL_STATUSES,
    ).values_list("discord_thread_id", flat=True)
    closed = 0
    for thread_id in stray_ids:
        if close_lp_buyback_thread_id(thread_id):
            closed += 1
    return closed


def auto_cancel_stalled_orders(now) -> int:
    """Cancel orders whose poster stalled 48h+ and was warned a day ago."""
    cancelled = 0
    stalled = _orders().filter(
        status__in=PRE_LP_STATUSES,
        status_changed_at__lte=now - AUTO_CANCEL_AFTER,
        stalled_reminder_at__lte=now - MIN_WARNING_BEFORE_CANCEL,
    )
    for order in stalled:
        if not poster_is_stalling(order):
            continue
        if auto_cancel_stalled_order(
            order.pk,
            stalled_before=now - AUTO_CANCEL_AFTER,
            reason=stalled_cancel_reason(order),
        ):
            cancelled += 1
            logger.info("Auto-cancelled stalled LP buyback order %s", order.pk)
    return cancelled


def _claim_reminder_slot(order, now) -> bool:
    """Stamp the reminder before posting so overlapping sweeps never double
    ping; the status match drops orders that moved since the query."""
    return bool(
        IndustryLoyaltyPointMarketOrder.objects.filter(
            pk=order.pk,
            status=order.status,
            stalled_reminder_at=order.stalled_reminder_at,
        ).update(stalled_reminder_at=now)
    )


def _release_reminder_slot(order, now) -> None:
    """Undo a stamp whose message never reached Discord.

    Auto-cancel keys off the stamp, so an undelivered warning must not count.
    """
    IndustryLoyaltyPointMarketOrder.objects.filter(
        pk=order.pk, stalled_reminder_at=now
    ).update(stalled_reminder_at=order.stalled_reminder_at)


def remind_stalled_orders(now) -> int:
    """Ping whoever owes the next step once the order has waited 24h.

    A stalling poster gets one reminder before auto-cancel. Claimers and ISK
    payers are never the reason for a cancel, so they are re-pinged daily.
    Orders without a thread wait for create_missing_threads.
    """
    reminded = 0
    stalled = _orders().filter(
        _not_reminded_since(now - REMIND_AFTER),
        status__in=STALLABLE_STATUSES,
        status_changed_at__lte=now - REMIND_AFTER,
        discord_thread_id__isnull=False,
    )
    for order in stalled:
        auto_cancels = poster_is_stalling(order)
        if auto_cancels and order.stalled_reminder_at is not None:
            continue
        if not _claim_reminder_slot(order, now):
            continue
        cancel_at = None
        if auto_cancels:
            cancel_at = max(
                order.status_changed_at + AUTO_CANCEL_AFTER,
                now + MIN_WARNING_BEFORE_CANCEL,
            )
        waited = now - order.status_changed_at
        delivered = post_stalled_reminder(
            order,
            waited_hours=int(waited.total_seconds() // 3600),
            cancel_at=cancel_at,
        )
        if not delivered:
            _release_reminder_slot(order, now)
            continue
        reminded += 1
    return reminded


def flag_stale_open_orders(now) -> int:
    """Weekly digest to the Conversion Team of orders nobody has taken."""
    stale = IndustryLoyaltyPointMarketOrder.objects.filter(
        _not_reminded_since(now - STALE_OPEN_AFTER),
        status=OPEN,
        status_changed_at__lte=now - STALE_OPEN_AFTER,
    )
    candidate_ids = list(stale.values_list("pk", flat=True))
    if not candidate_ids:
        return 0
    # One stamp for the batch; the re-applied filter skips any order an
    # overlapping sweep stamped in between.
    stale.filter(pk__in=candidate_ids).update(stalled_reminder_at=now)
    due = list(
        _orders()
        .filter(pk__in=candidate_ids, status=OPEN, stalled_reminder_at=now)
        .order_by("status_changed_at", "id")
    )
    if not due:
        return 0
    if not post_stale_open_orders_digest(due, now=now):
        # Release the slots so the next sweep tries again.
        IndustryLoyaltyPointMarketOrder.objects.filter(
            pk__in=[order.pk for order in due], stalled_reminder_at=now
        ).update(stalled_reminder_at=None)
        return 0
    return len(due)


def sweep_lp_buyback_orders(now=None) -> dict:
    now = now or timezone.now()
    stats = {
        "threads_created": 0,
        "threads_closed": 0,
        "cancelled": 0,
        "reminded": 0,
        "stale_open_flagged": 0,
    }
    if lp_buyback_channel_id():
        stats["threads_created"] = create_missing_threads(now)
        stats["threads_closed"] = close_stray_threads()
    # Cancel before reminding so one sweep never warns and cancels at once.
    stats["cancelled"] = auto_cancel_stalled_orders(now)
    stats["reminded"] = remind_stalled_orders(now)
    if lp_conversion_alert_channel_id():
        stats["stale_open_flagged"] = flag_stale_open_orders(now)
    logger.info("LP buyback sweep: %s", stats)
    return stats
