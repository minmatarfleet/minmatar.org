"""Celery tasks for industry: jobs sync and cost-index cache."""

import logging

from app.celery import app
from eveonline.helpers.characters.update import update_character_industry_jobs
from eveonline.models import EveCharacter

from industry.helpers.cost_indices import sync_industry_system_cost_indices
from industry.helpers.loyalty_store import (
    ensure_loyalty_store_offers_for_product,
    sync_loyalty_store_offers,
)
from industry.models import IndustryOrderItemAssignment

logger = logging.getLogger(__name__)


@app.task()
def sync_industry_jobs_for_character(character_id: int) -> None:
    """Fetch and store industry jobs for a single character from ESI (EveCharacterIndustryJob)."""
    try:
        update_character_industry_jobs(character_id)
    except Exception as e:
        logger.exception(
            "Failed to sync industry jobs for character %s: %s",
            character_id,
            e,
        )


@app.task()
def sync_industry_jobs_for_order_assignees() -> None:
    """
    For every character assigned to part of an industry order, sync industry
    jobs for that character and all their related characters (same user).
    Runs every 4 hours via Celery beat.
    """
    # Distinct character PKs that have at least one assignment
    assigned_character_pks = set(
        IndustryOrderItemAssignment.objects.values_list(
            "character_id", flat=True
        ).distinct()
    )

    assigned_rows = EveCharacter.objects.filter(
        pk__in=assigned_character_pks
    ).values_list("user_id", "character_id")

    character_ids = set()
    user_ids = {user_id for user_id, _ in assigned_rows if user_id}
    for _, character_id in assigned_rows:
        character_ids.add(character_id)

    if user_ids:
        character_ids.update(
            EveCharacter.objects.filter(user_id__in=user_ids).values_list(
                "character_id", flat=True
            )
        )

    for character_id in character_ids:
        sync_industry_jobs_for_character.delay(character_id)

    logger.info(
        "Scheduled industry job sync for %s character(s) (order assignees and related)",
        len(character_ids),
    )


@app.task()
def sync_industry_system_cost_indices_task() -> int:
    """
    Refresh cached ESI industry cost indices for all solar systems.

    Hourly via Celery beat so planner requests read the DB instead of ESI.
    """
    try:
        return sync_industry_system_cost_indices()
    except Exception:
        logger.exception("Failed to sync industry system cost indices")
        raise


@app.task()
def sync_loyalty_store_offers_task() -> int:
    """
    Refresh cached pure LP+ISK loyalty-store offers.

    Manual / admin / product-save driven — not on a beat schedule.
    """
    try:
        return sync_loyalty_store_offers()
    except Exception:
        logger.exception("Failed to sync loyalty store offers")
        raise


@app.task()
def ensure_loyalty_store_offers_for_product_task(product_id: int) -> int:
    """Ensure LP store offers exist after a navy IndustryProduct is saved."""
    try:
        return ensure_loyalty_store_offers_for_product(int(product_id))
    except Exception:
        logger.exception(
            "Failed to ensure loyalty store offers for product %s",
            product_id,
        )
        raise
