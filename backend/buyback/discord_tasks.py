"""Celery tasks that mirror hangar purchase orders onto Discord."""

from __future__ import annotations

import logging

from celery import shared_task

from buyback.helpers.purchase_discord import (
    notify_purchase_created,
    notify_purchase_status_changed,
)
from buyback.models import BuybackPurchaseOrder

logger = logging.getLogger(__name__)


def _order_for_notify(order_id: int) -> BuybackPurchaseOrder | None:
    return (
        BuybackPurchaseOrder.objects.select_related(
            "created_by",
            "created_by__discord_user",
            "completed_by",
            "completed_by__discord_user",
        )
        .prefetch_related("lines")
        .filter(pk=order_id)
        .first()
    )


@shared_task
def notify_buyback_purchase_created_task(order_id: int) -> None:
    """Create a Discord forum thread for a new hangar purchase order."""
    order = _order_for_notify(order_id)
    if order is None:
        logger.warning(
            "Hangar purchase %s not found for Discord create notify",
            order_id,
        )
        return
    try:
        notify_purchase_created(order)
    except Exception:
        logger.exception(
            "Failed Discord create notify for hangar purchase %s", order_id
        )
        raise


@shared_task
def notify_buyback_purchase_status_changed_task(order_id: int) -> None:
    """Post Discord status and archive the hangar purchase thread."""
    order = _order_for_notify(order_id)
    if order is None:
        logger.warning(
            "Hangar purchase %s not found for Discord status notify",
            order_id,
        )
        return
    try:
        notify_purchase_status_changed(order)
    except Exception:
        logger.exception(
            "Failed Discord status notify for hangar purchase %s", order_id
        )
        raise
