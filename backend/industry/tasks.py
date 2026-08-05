"""Celery tasks for industry: jobs sync and cost-index cache."""

import logging

from app.celery import app
from eveonline.helpers.characters.update import update_character_industry_jobs
from eveonline.models import EveCharacter

from industry.helpers.contract_associations import (
    reconcile_associations_for_character,
    reconcile_open_order_contract_associations,
)
from industry.helpers.cost_indices import sync_industry_system_cost_indices
from industry.helpers.loyalty_store import (
    ensure_loyalty_store_offers_for_product,
    sync_loyalty_store_offers,
)
from industry.helpers.lp_store_offer_economics_rebuild import (
    rebuild_lp_store_offer_economics,
)
from industry.helpers.notifications import (
    emit_order_created,
    emit_order_jobs_for_created_job_ids,
)
from industry.helpers.order_profit_breakdown import (
    can_refresh_order_profit_breakdown,
    refresh_order_profit_breakdown,
)
from industry.models import IndustryOrder, IndustryOrderItemAssignment

logger = logging.getLogger(__name__)


@app.task()
def compute_order_profit_breakdown_task(order_id: int) -> bool:
    """
    Compute and store the order profit/price snapshot off the request thread.

    Refresh is allowed while the order is open, or once when no snapshot
    exists yet (including fulfilled orders that never got one).
    """
    try:
        order = IndustryOrder.objects.get(pk=order_id)
    except IndustryOrder.DoesNotExist:
        logger.warning(
            "Order %s not found for profit breakdown compute", order_id
        )
        return False
    if not can_refresh_order_profit_breakdown(order):
        return False
    try:
        refresh_order_profit_breakdown(order)
        return True
    except Exception:
        logger.exception(
            "Failed to store profit breakdown for order %s", order_id
        )
        return False


@app.task()
def emit_order_created_notification(
    order_id: int, creator_user_id: int | None = None
) -> int:
    """
    Fan-out industry.order.created off the request/admin thread.

    Safe to call again after tribe_groups are assigned — idempotency keys
    skip users already notified for this order.
    """
    try:
        order = IndustryOrder.objects.select_related("character").get(
            pk=order_id
        )
    except IndustryOrder.DoesNotExist:
        logger.warning("Order %s not found for created notification", order_id)
        return 0
    try:
        deliveries = emit_order_created(order, creator_user_id=creator_user_id)
        return len(deliveries)
    except Exception:
        logger.exception(
            "Failed to emit new-order notification for order %s", order_id
        )
        raise


@app.task()
def emit_order_job_notifications_for_jobs(created_job_ids: list[int]) -> int:
    """Fan-out from character update / job sync when new ESI jobs are created."""
    try:
        return emit_order_jobs_for_created_job_ids(created_job_ids or [])
    except Exception:
        logger.exception(
            "Failed to emit order-job notifications for jobs %s",
            created_job_ids,
        )
        raise


@app.task()
def sync_industry_jobs_for_character(character_id: int) -> None:
    """Fetch and store industry jobs for a single character from ESI (EveCharacterIndustryJob)."""
    try:
        created_job_ids = update_character_industry_jobs(character_id)[1]
    except Exception as e:
        logger.exception(
            "Failed to sync industry jobs for character %s: %s",
            character_id,
            e,
        )
        return

    emit_order_jobs_for_created_job_ids(created_job_ids)


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
    Refresh cached loyalty-store offers (full ESI catalog).

    Periodic via Celery beat; also admin action / product-save / planner miss.
    Rebuilds economics snapshot afterwards from local price data.
    """
    try:
        count = sync_loyalty_store_offers()
        rebuild_lp_store_offer_economics_task.delay()
        return count
    except Exception:
        logger.exception("Failed to sync loyalty store offers")
        raise


@app.task()
def rebuild_lp_store_offer_economics_task() -> int:
    """
    Rebuild LP store offer economics snapshot from local caches (no ESI).

    Hourly Celery beat; also after ESI offer sync.
    """
    try:
        return rebuild_lp_store_offer_economics()
    except Exception:
        logger.exception("Failed to rebuild LP store offer economics")
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


@app.task()
def reconcile_industry_contract_associations_task() -> int:
    """
    Score and upsert soft links between open industry orders and ESI contracts.

    Periodic via Celery beat. Does not mark assignments delivered.
    """
    try:
        return reconcile_open_order_contract_associations(fetch_items=True)
    except Exception:
        logger.exception("Failed to reconcile industry contract associations")
        raise


@app.task()
def reconcile_industry_contract_associations_for_character_task(
    character_id: int,
) -> int:
    """Reconcile associations for open orders owned by this ESI character_id."""
    try:
        return reconcile_associations_for_character(
            int(character_id), fetch_items=True
        )
    except Exception:
        logger.exception(
            "Failed to reconcile industry contract associations for character %s",
            character_id,
        )
        raise
