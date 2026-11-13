"""Hourly hangar-sale housekeeping: thread mirror, reminders, auto-cancel.

- Contract not up yet, on a new sale: one reminder at 24h, cancel at 48h.
  The stock is still reserved and no in-game contract has been confirmed.
  Sales already open keep a Close button for the team and are not swept.
- Contract is up (buyer owes Contract accepted): pinged every 24h, never
  cancelled. Cancelling then would strand the contract.
- A thread missing 10 minutes after the order is created again.
- A thread still open for a completed or cancelled order is archived.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from buyback.helpers.purchase_discord import (
    active_buyback_thread_ids,
    buyback_channel_id,
    close_thread_id,
    notify_purchase_created,
    post_stalled_reminder,
    stalled_cancel_reason,
)
from buyback.helpers.purchase_orders import cancel_stalled_contract_up
from buyback.models import BuybackPurchaseOrder

logger = logging.getLogger(__name__)

REMIND_AFTER = timedelta(hours=24)
AUTO_CANCEL_AFTER = timedelta(hours=48)
# Pilots always get a full day's warning, even for sales already stalled
# past 48h when this sweep first ran.
MIN_WARNING_BEFORE_CANCEL = AUTO_CANCEL_AFTER - REMIND_AFTER
# Leave the create task time to run before treating a thread as missing.
MISSING_THREAD_GRACE = timedelta(minutes=10)

Status = BuybackPurchaseOrder.Status
Step = BuybackPurchaseOrder.SettlementStep


def _not_reminded_since(cutoff) -> Q:
    return Q(stalled_reminder_at__isnull=True) | Q(
        stalled_reminder_at__lte=cutoff
    )


def _orders():
    return BuybackPurchaseOrder.objects.select_related(
        "created_by", "created_by__discord_user"
    ).prefetch_related("lines")


def _can_auto_cancel(order: BuybackPurchaseOrder) -> bool:
    # Threads already open before Contract up are closed by the team.
    return (
        order.status == Status.PENDING
        and order.settlement_step == Step.CONTRACT_UP
        and order.team_prompted
    )


def create_missing_threads(now) -> int:
    """Retry thread creation for pending sales whose create task failed."""
    created = 0
    missing = _orders().filter(
        status=Status.PENDING,
        discord_thread_id__isnull=True,
        created_at__lte=now - MISSING_THREAD_GRACE,
    )
    for order in missing:
        notify_purchase_created(order)
        order.refresh_from_db(fields=["discord_thread_id"])
        if order.discord_thread_id:
            created += 1
            logger.info(
                "Created missing buyback sale thread for order %s", order.pk
            )
    return created


def close_stray_threads() -> int:
    """Archive forum threads still open for completed or cancelled sales."""
    active_ids = active_buyback_thread_ids()
    if not active_ids:
        return 0
    stray_ids = BuybackPurchaseOrder.objects.filter(
        discord_thread_id__in=active_ids,
        status__in=(Status.COMPLETED, Status.CANCELLED),
    ).values_list("discord_thread_id", flat=True)
    closed = 0
    for thread_id in stray_ids:
        if close_thread_id(thread_id):
            closed += 1
    return closed


def auto_cancel_stalled_orders(now) -> int:
    """Cancel sales whose contract was never put up, after a day's warning."""
    cancelled = 0
    stalled = _orders().filter(
        status=Status.PENDING,
        settlement_step=Step.CONTRACT_UP,
        team_prompted=True,
        settlement_changed_at__lte=now - AUTO_CANCEL_AFTER,
        stalled_reminder_at__lte=now - MIN_WARNING_BEFORE_CANCEL,
    )
    for order in stalled:
        if not _can_auto_cancel(order):
            continue
        if cancel_stalled_contract_up(
            order.pk,
            stalled_before=now - AUTO_CANCEL_AFTER,
            reason=stalled_cancel_reason(order),
        ):
            cancelled += 1
            logger.info("Auto-cancelled stalled buyback sale %s", order.pk)
    return cancelled


def _claim_reminder_slot(order, now) -> bool:
    """Stamp the reminder before posting so overlapping sweeps never double
    ping; the step match drops sales that moved since the query."""
    return bool(
        BuybackPurchaseOrder.objects.filter(
            pk=order.pk,
            status=Status.PENDING,
            settlement_step=order.settlement_step,
            stalled_reminder_at=order.stalled_reminder_at,
        ).update(stalled_reminder_at=now)
    )


def _release_reminder_slot(order, now) -> None:
    """Undo a stamp whose message never reached Discord.

    Auto-cancel keys off the stamp, so an undelivered warning must not count.
    """
    BuybackPurchaseOrder.objects.filter(
        pk=order.pk, stalled_reminder_at=now
    ).update(stalled_reminder_at=order.stalled_reminder_at)


def remind_stalled_orders(now) -> int:
    """Ping whoever owes the next button once the sale has waited 24h.

    A sale still waiting on Contract up gets one reminder, then auto-cancel.
    Once the contract is up the buyer is re-pinged daily and never cancelled.
    Sales without a thread wait for create_missing_threads.
    """
    reminded = 0
    stalled = _orders().filter(
        _not_reminded_since(now - REMIND_AFTER),
        Q(settlement_step=Step.AWAITING_ACCEPT)
        | Q(settlement_step=Step.CONTRACT_UP, team_prompted=True),
        status=Status.PENDING,
        settlement_changed_at__lte=now - REMIND_AFTER,
        discord_thread_id__isnull=False,
    )
    for order in stalled:
        auto_cancels = _can_auto_cancel(order)
        if auto_cancels and order.stalled_reminder_at is not None:
            continue
        if not _claim_reminder_slot(order, now):
            continue
        cancel_at = None
        if auto_cancels:
            cancel_at = max(
                order.settlement_changed_at + AUTO_CANCEL_AFTER,
                now + MIN_WARNING_BEFORE_CANCEL,
            )
        waited = now - order.settlement_changed_at
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


def sweep_buyback_purchase_orders(now=None) -> dict:
    now = now or timezone.now()
    stats = {
        "threads_created": 0,
        "threads_closed": 0,
        "cancelled": 0,
        "reminded": 0,
    }
    if buyback_channel_id():
        stats["threads_created"] = create_missing_threads(now)
        stats["threads_closed"] = close_stray_threads()
    # Cancel before reminding so one sweep never warns and cancels at once.
    stats["cancelled"] = auto_cancel_stalled_orders(now)
    stats["reminded"] = remind_stalled_orders(now)
    logger.info("Buyback sale sweep: %s", stats)
    return stats
