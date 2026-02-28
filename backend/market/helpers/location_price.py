"""Fetch market orders from ESI and update EveMarketItemLocationPrice.

Supports both Upwell structures (structure markets API) and NPC stations
(region orders API). Does not touch EveMarketItemOrder. Fetches orders in
memory, computes lowest sell / highest buy (station-range only) / split
per item, and writes only to EveMarketItemLocationPrice.
"""

import logging
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from eveonline.client import EsiClient, get_region_market_orders_pages
from eveonline.models import EveLocation
from eveuniverse.models import EveType

from market.models import EveMarketItemLocationPrice

logger = logging.getLogger(__name__)

# Only station-range buy orders count for buy_price (exclude region-wide lowballs)
BUY_RANGE_OK = frozenset({"", "station"})


def _ensure_eve_types(type_ids, types_cache):
    missing = [tid for tid in type_ids if tid not in types_cache]
    if not missing:
        return
    existing = {t.id: t for t in EveType.objects.filter(id__in=missing)}
    types_cache.update(existing)
    for type_id in missing:
        if type_id not in types_cache:
            eve_type, _ = EveType.objects.get_or_create_esi(id=type_id)
            types_cache[type_id] = eve_type


def _aggregate_orders_into_prices(page_orders, location_id: int | None):
    """
    Build sell_min and buy_max dicts from a sequence of order dicts.
    If location_id is set, only include orders with order['location_id'] == location_id (for region/station).
    """
    sell_min: dict[int, Decimal] = {}
    buy_max: dict[int, Decimal] = {}
    for o in page_orders:
        if location_id is not None and o.get("location_id") != location_id:
            continue
        type_id = o["type_id"]
        price = Decimal(str(o["price"]))
        is_buy = bool(o.get("is_buy_order", True))
        raw_range = o.get("range")
        order_range = str(raw_range).lower() if raw_range is not None else ""

        if is_buy:
            if order_range in BUY_RANGE_OK:
                if type_id not in buy_max or price > buy_max[type_id]:
                    buy_max[type_id] = price
        else:
            if type_id not in sell_min or price < sell_min[type_id]:
                sell_min[type_id] = price
    return sell_min, buy_max


def _merge_aggregates(acc_sell, acc_buy, sell_min, buy_max):
    """Merge (sell_min, buy_max) into (acc_sell, acc_buy) in place."""
    for tid, price in sell_min.items():
        if tid not in acc_sell or price < acc_sell[tid]:
            acc_sell[tid] = price
    for tid, price in buy_max.items():
        if tid not in acc_buy or price > acc_buy[tid]:
            acc_buy[tid] = price


def _fetch_orders_into_aggregates(
    location, character_id: int | None, filter_type_id: int | None
) -> tuple[dict[int, Decimal], dict[int, Decimal]] | None:
    """Fetch ESI orders for location into sell_min and buy_max. Returns None on failure."""
    sell_min: dict[int, Decimal] = {}
    buy_max: dict[int, Decimal] = {}
    if location.is_structure:
        if character_id is None:
            logger.warning(
                "Character required for structure location %s, skipping",
                location.location_id,
            )
            return None
        for page_data in EsiClient(
            character_id
        ).get_structure_market_orders_pages(location.location_id):
            if page_data is None:
                return None
            s, b = _aggregate_orders_into_prices(page_data, location_id=None)
            _merge_aggregates(sell_min, buy_max, s, b)
    else:
        if location.region_id is None:
            logger.warning(
                "Region required for station location %s (%s), skipping",
                location.location_id,
                location.location_name,
            )
            return None
        for page_data in get_region_market_orders_pages(
            location.region_id, type_id=filter_type_id
        ):
            if page_data is None:
                return None
            s, b = _aggregate_orders_into_prices(
                page_data, location_id=location.location_id
            )
            _merge_aggregates(sell_min, buy_max, s, b)
    return sell_min, buy_max


def _persist_location_prices(
    location_id: int,
    type_ids: list[int],
    sell_min: dict,
    buy_max: dict,
    filter_type_id: int | None,
) -> int:
    """Delete stale rows, create/update EveMarketItemLocationPrice. Returns count of rows written."""
    if not type_ids:
        if filter_type_id is not None:
            EveMarketItemLocationPrice.objects.filter(
                location_id=location_id, item_id=filter_type_id
            ).delete()
        else:
            EveMarketItemLocationPrice.objects.filter(
                location_id=location_id
            ).delete()
        return 0

    types_cache: dict[int, EveType] = {}
    _ensure_eve_types(type_ids, types_cache)

    now = timezone.now()
    to_create = []
    to_update = []

    if filter_type_id is None:
        EveMarketItemLocationPrice.objects.filter(
            location_id=location_id
        ).exclude(item_id__in=type_ids).delete()

    for tid in type_ids:
        if tid not in types_cache:
            continue
        sell_price = sell_min[tid]
        buy_price = buy_max.get(tid)
        split_price = (
            (sell_price + buy_price) / 2 if buy_price is not None else None
        )

        existing = EveMarketItemLocationPrice.objects.filter(
            location_id=location_id, item_id=tid
        ).first()
        if existing:
            existing.sell_price = sell_price
            existing.buy_price = buy_price
            existing.split_price = split_price
            existing.updated_at = now
            to_update.append(existing)
        else:
            to_create.append(
                EveMarketItemLocationPrice(
                    location_id=location_id,
                    item_id=tid,
                    sell_price=sell_price,
                    buy_price=buy_price,
                    split_price=split_price,
                    updated_at=now,
                )
            )

    with transaction.atomic():
        if to_update:
            EveMarketItemLocationPrice.objects.bulk_update(
                to_update,
                ["sell_price", "buy_price", "split_price", "updated_at"],
            )
        if to_create:
            EveMarketItemLocationPrice.objects.bulk_create(to_create)

    n = len(to_create) + len(to_update)
    logger.info(
        "Location prices updated: location_id=%s %s row(s)",
        location_id,
        n,
    )
    return n


def fetch_and_update_market_location_prices(
    character_id: int | None, location_id: int, type_id: int | None = None
) -> int:
    """
    Fetch market orders from ESI for the given location (structure or
    station), compute lowest sell, highest buy (station-range only), and
    split per item in memory, then update EveMarketItemLocationPrice.
    Does not read or write EveMarketItemOrder.

    - If location.is_structure: use structure markets API (requires character_id).
    - Else: use region orders API (no auth), filter by location_id; requires location.region_id.
      Optional type_id: fetch only that type (fewer pages, for single-type update or testing).

    Returns the number of EveMarketItemLocationPrice rows created or
    updated. Returns 0 if location not found or fetch fails.
    """
    location = EveLocation.objects.filter(location_id=location_id).first()
    if not location:
        logger.warning(
            "Location %s not found for location price update", location_id
        )
        return 0

    aggregates = _fetch_orders_into_aggregates(location, character_id, type_id)
    if aggregates is None:
        return 0
    sell_min, buy_max = aggregates
    type_ids = list(sell_min.keys())
    return _persist_location_prices(
        location_id, type_ids, sell_min, buy_max, type_id
    )
