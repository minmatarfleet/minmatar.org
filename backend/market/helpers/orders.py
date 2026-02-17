"""Helpers for syncing market sell orders used by item seeding."""

import logging
from decimal import Decimal

from django.db import transaction
from django.db.models import Q

from eveonline.client import EsiClient
from eveonline.models import EveLocation
from eveuniverse.models import EveType

from market.models import EveMarketItemOrder

logger = logging.getLogger(__name__)


def _ensure_eve_types(type_ids, types_cache):
    """
    Ensure EveType exists for each type_id; update types_cache in place.
    Returns the cache (for convenience).
    """
    missing = [tid for tid in type_ids if tid not in types_cache]
    if not missing:
        return types_cache
    existing = {t.id: t for t in EveType.objects.filter(id__in=missing)}
    types_cache.update(existing)
    for type_id in missing:
        if type_id not in types_cache:
            eve_type, _ = EveType.objects.get_or_create_esi(id=type_id)
            types_cache[type_id] = eve_type
    return types_cache


def clear_structure_sell_orders_for_location(
    location_id: int, task_uid: str
) -> int:
    """
    Delete EveMarketItemOrder rows for the given location that were not
    imported by the given task_uid (i.e. from previous runs or other tasks).
    Returns the number deleted.
    """
    qs = EveMarketItemOrder.objects.filter(location_id=location_id).filter(
        Q(imported_by_task_uid__isnull=True)
        | ~Q(imported_by_task_uid=task_uid)
    )
    deleted, _ = qs.delete()
    return deleted


def process_structure_sell_orders_page(
    character_id: int, location_id: int, page: int, task_uid: str
) -> tuple[int, int]:
    """
    Fetch a single page of structure market orders and insert sell orders
    for that page with imported_by_task_uid=task_uid. Before inserting,
    deletes existing orders for the same (location, items on this page)
    that were not imported by this task_uid. Uses ignore_conflicts so
    parallel page tasks do not raise on duplicate order_id. Returns
    (orders_attempted, total_volume) for the batch.
    """
    location = EveLocation.objects.filter(location_id=location_id).first()
    if not location:
        logger.warning(
            "Location %s not found, skipping page %s", location_id, page
        )
        return 0, 0

    client = EsiClient(character_id)
    response = client.get_structure_market_orders_page(location_id, page)
    if not response.success():
        logger.warning(
            "Failed to fetch structure market orders location_id=%s page=%s: %s",
            location_id,
            page,
            response.response_code,
        )
        return 0, 0

    page_data = response.results() or []
    sell_orders = [o for o in page_data if not o.get("is_buy_order", True)]
    if not sell_orders:
        return 0, 0

    type_ids_page = {o["type_id"] for o in sell_orders}
    types_cache = {}
    _ensure_eve_types(type_ids_page, types_cache)

    to_create = []
    for o in sell_orders:
        if o["type_id"] not in types_cache:
            continue
        order_id = o.get("order_id")
        to_create.append(
            EveMarketItemOrder(
                order_id=order_id,
                item_id=o["type_id"],
                location=location,
                price=Decimal(str(o["price"])),
                quantity=int(o.get("volume_remain", o.get("volume_total", 0))),
                issuer_external_id=o.get("issuer"),  # ESI may provide issuer
                imported_by_task_uid=task_uid,
                imported_page=page,
            )
        )

    if not to_create:
        return 0, 0

    type_ids_inserting = {obj.item_id for obj in to_create}
    with transaction.atomic():
        EveMarketItemOrder.objects.filter(
            location_id=location_id,
            item_id__in=type_ids_inserting,
        ).filter(
            Q(imported_by_task_uid__isnull=True)
            | ~Q(imported_by_task_uid=task_uid)
        ).delete()
        EveMarketItemOrder.objects.bulk_create(
            to_create, ignore_conflicts=True
        )

    total_volume = sum(obj.quantity for obj in to_create)
    logger.info(
        "Structure sell orders page complete: location_id=%s page=%s "
        "orders_created=%s total_volume=%s task_uid=%s",
        location_id,
        page,
        len(to_create),
        total_volume,
        task_uid[:8] if task_uid else None,
    )
    return len(to_create), total_volume
