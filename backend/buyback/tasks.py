"""Celery tasks for buyback ledger and weekly metrics."""

from __future__ import annotations

import logging

from celery import shared_task

from buyback.discord_tasks import (  # noqa: F401  # pylint: disable=unused-import
    notify_buyback_purchase_created_task,
    notify_buyback_purchase_status_changed_task,
)
from buyback.helpers.refresh import refresh_buyback_ledger

logger = logging.getLogger(__name__)


@shared_task
def sync_buyback_ledger_task():
    """Hourly-ish: contracts in/out, sell fills, hangar snapshot → Unknown."""
    result = refresh_buyback_ledger(
        sync_contracts=True,
        sync_sell_orders=True,
        snapshot_hangar=True,
        refresh_metrics=False,
        seed_allowlist=False,
    )
    logger.info("sync_buyback_ledger_task done: %s", result)
    return result


@shared_task
def refresh_buyback_accepted_item_metrics_task():
    """Monday: seed allowlist + demand/stockpile metrics on accepted items."""
    result = refresh_buyback_ledger(
        sync_contracts=False,
        sync_sell_orders=False,
        snapshot_hangar=True,
        refresh_metrics=True,
        seed_allowlist=True,
    )
    logger.info("refresh_buyback_accepted_item_metrics_task done: %s", result)
    return result
