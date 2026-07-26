"""Atomic structure order-book sync with inferred-sales diff."""

from __future__ import annotations

import logging
from datetime import datetime

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from eveonline.client import EsiClient
from eveonline.models import EveLocation

from market.helpers.inferred_sales import (
    infer_sales_from_snapshots,
    orders_from_db_rows,
    parse_esi_order,
    prune_inferred_sales,
)
from market.helpers.orders import _ensure_eve_types
from market.helpers.pricing import get_prices_by_type_id
from market.models import (
    EveMarketInferredSale,
    EveMarketItemOrder,
    EveMarketOrderBookSync,
)

logger = logging.getLogger(__name__)

ORDER_BOOK_SYNC_LOCK_TTL = 600
ORDER_BOOK_SYNC_LOCK_PREFIX = "market:order_book_sync:"


def _lock_key(location_id: int) -> str:
    return f"{ORDER_BOOK_SYNC_LOCK_PREFIX}{location_id}"


def fetch_structure_orders_for_location(
    character_id: int, location_id: int
) -> list[dict] | None:
    """
    Fetch all structure market order pages for a location.

    Returns a list of order dicts, or None if the token/request failed.
    """
    client = EsiClient(character_id)
    orders: list[dict] = []
    for page_data in client.get_structure_market_orders_pages(location_id):
        if page_data is None:
            logger.warning(
                "Failed to fetch structure orders for location_id=%s "
                "(invalid token or ESI error)",
                location_id,
            )
            return None
        orders.extend(page_data)
    return orders


def apply_order_book_snapshot(
    location: EveLocation,
    order_dicts: list[dict],
    *,
    now: datetime | None = None,
    baseline_by_type: dict[int, int] | None = None,
) -> tuple[int, int]:
    """
    Diff previous DB orders against the new book, write inferred sales,
    replace the location's order snapshot, and stamp the sync watermark.

    Returns (sales_created, orders_written).
    """
    now = now or timezone.now()
    location_id = location.location_id

    previous_rows = list(
        EveMarketItemOrder.objects.filter(location_id=location_id)
    )
    sync = EveMarketOrderBookSync.objects.filter(
        location_id=location_id
    ).first()
    previous_synced_at = sync.last_synced_at if sync else None

    previous = orders_from_db_rows(previous_rows)
    current: list = []
    for raw in order_dicts:
        parsed = parse_esi_order(raw)
        if parsed is not None:
            current.append(parsed)

    type_ids = {o.type_id for o in previous} | {o.type_id for o in current}
    if baseline_by_type is None and type_ids:
        baseline_by_type = get_prices_by_type_id(list(type_ids))
    elif baseline_by_type is None:
        baseline_by_type = {}

    drafts = infer_sales_from_snapshots(
        previous,
        current,
        previous_synced_at,
        now,
        baseline_by_type=baseline_by_type,
    )

    types_cache: dict = {}
    _ensure_eve_types(type_ids, types_cache)

    sale_objs = [
        EveMarketInferredSale(
            location=location,
            item_id=draft.type_id,
            quantity=draft.quantity,
            price=draft.price,
            inferred_at=now,
            order_id=draft.order_id,
            reason=draft.reason,
        )
        for draft in drafts
        if draft.type_id in types_cache
    ]

    order_objs = []
    for raw in order_dicts:
        parsed = parse_esi_order(raw)
        if parsed is None or parsed.type_id not in types_cache:
            continue
        order_objs.append(
            EveMarketItemOrder(
                order_id=parsed.order_id,
                item_id=parsed.type_id,
                location=location,
                price=parsed.price,
                quantity=parsed.volume_remain,
                is_buy_order=parsed.is_buy_order,
                issuer_external_id=raw.get("issuer"),
                issued=parsed.issued,
                duration_days=parsed.duration_days,
            )
        )

    with transaction.atomic():
        if sale_objs:
            EveMarketInferredSale.objects.bulk_create(sale_objs)
        EveMarketItemOrder.objects.filter(location_id=location_id).delete()
        if order_objs:
            EveMarketItemOrder.objects.bulk_create(order_objs)
        EveMarketOrderBookSync.objects.update_or_create(
            location_id=location_id,
            defaults={"last_synced_at": now},
        )

    logger.info(
        "Order book snapshot applied: location_id=%s sales=%s orders=%s",
        location_id,
        len(sale_objs),
        len(order_objs),
    )
    return len(sale_objs), len(order_objs)


def sync_structure_order_book_for_location(
    character_id: int, location_id: int
) -> tuple[int, int] | None:
    """
    Lock, fetch, apply snapshot, and prune old inferred sales for one location.

    Returns (sales_created, orders_written), or None if lock/fetch skipped.
    """
    lock_key = _lock_key(location_id)
    if not cache.add(lock_key, "1", timeout=ORDER_BOOK_SYNC_LOCK_TTL):
        logger.info(
            "Order book sync already in progress for location_id=%s, skipping",
            location_id,
        )
        return None

    try:
        location = EveLocation.objects.filter(location_id=location_id).first()
        if not location:
            logger.warning(
                "Location %s not found, skipping order book sync", location_id
            )
            return None

        order_dicts = fetch_structure_orders_for_location(
            character_id, location_id
        )
        if order_dicts is None:
            return None

        sales, orders = apply_order_book_snapshot(location, order_dicts)
        prune_inferred_sales()
        return sales, orders
    finally:
        cache.delete(lock_key)
