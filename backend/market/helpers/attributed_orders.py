"""Sync character and corporation open market orders into EveMarketAttributedOrder."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Callable, Iterable

from django.utils import timezone

from eveonline.client import EsiClient
from eveonline.constants import ALLIED_ALLIANCE_NAMES
from eveonline.helpers.characters import market_scope_character_ids
from eveonline.helpers.corporations import get_director_with_scope
from eveonline.helpers.db_sync import replace_with_bulk_create
from eveonline.helpers.esi import parse_esi_date
from eveonline.models import EveCharacter, EveCorporation
from market.helpers.market_operators import eligible_market_operator_user_ids
from market.models import EveMarketAttributedOrder

logger = logging.getLogger(__name__)

SCOPE_CORPORATION_ORDERS = ["esi-markets.read_corporation_orders.v1"]


class OrderSyncStatus(str, Enum):
    OK = "ok"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass(frozen=True)
class OrderSyncResult:
    status: OrderSyncStatus
    rows: int = 0


def _order_from_esi(
    *,
    raw: dict,
    owner_character_id: int,
    corporation_id: int | None,
    synced_at,
) -> EveMarketAttributedOrder | None:
    order_id = raw.get("order_id")
    type_id = raw.get("type_id")
    location_id = raw.get("location_id")
    price = raw.get("price")
    volume_remain = raw.get("volume_remain")
    if (
        order_id is None
        or type_id is None
        or location_id is None
        or price is None
        or volume_remain is None
    ):
        return None
    return EveMarketAttributedOrder(
        order_id=int(order_id),
        type_id=int(type_id),
        location_esi_id=int(location_id),
        price=Decimal(str(price)),
        volume_remain=int(volume_remain),
        is_buy_order=bool(raw.get("is_buy_order", False)),
        issued=parse_esi_date(raw.get("issued")),
        duration_days=raw.get("duration"),
        owner_character_id=int(owner_character_id),
        corporation_id=corporation_id,
        synced_at=synced_at,
    )


def _replace_orders_from_esi(
    *,
    raw_orders: Iterable[dict],
    owner_for: Callable[[dict], int | None],
    corporation_id: int | None,
    delete_queryset,
) -> OrderSyncResult:
    synced_at = timezone.now()
    instances = []
    for raw in raw_orders:
        owner_character_id = owner_for(raw)
        if owner_character_id is None:
            continue
        order = _order_from_esi(
            raw=raw,
            owner_character_id=owner_character_id,
            corporation_id=corporation_id,
            synced_at=synced_at,
        )
        if order:
            instances.append(order)
    rows = replace_with_bulk_create(
        delete_queryset=delete_queryset,
        instances=instances,
    )
    return OrderSyncResult(status=OrderSyncStatus.OK, rows=rows)


def sync_character_orders(character_id: int) -> OrderSyncResult:
    """Replace personal open orders for one character."""
    character = EveCharacter.objects.filter(character_id=character_id).first()
    if not character:
        logger.warning("Character %s not found for order sync", character_id)
        return OrderSyncResult(status=OrderSyncStatus.FAILED)

    response = EsiClient(character).get_character_orders()
    if not response.success():
        logger.warning(
            "ESI character orders failed for %s: %s",
            character_id,
            response.response_code,
        )
        return OrderSyncResult(status=OrderSyncStatus.FAILED)

    return _replace_orders_from_esi(
        raw_orders=response.results() or [],
        owner_for=lambda _raw: character_id,
        corporation_id=None,
        delete_queryset=EveMarketAttributedOrder.objects.filter(
            owner_character_id=character_id,
            corporation_id__isnull=True,
        ),
    )


def sync_corporation_orders(corporation_id: int) -> OrderSyncResult:
    """Replace corp open orders; attribute via ESI issued_by."""
    corporation = (
        EveCorporation.objects.filter(corporation_id=corporation_id)
        .select_related("ceo")
        .prefetch_related("directors")
        .first()
    )
    if not corporation:
        logger.warning(
            "Corporation %s not found for order sync", corporation_id
        )
        return OrderSyncResult(status=OrderSyncStatus.FAILED)

    director = get_director_with_scope(corporation, SCOPE_CORPORATION_ORDERS)
    if not director:
        logger.debug(
            "Corporation %s has no director with corporation orders scope",
            corporation_id,
        )
        return OrderSyncResult(status=OrderSyncStatus.SKIPPED)

    response = EsiClient(director).get_corporation_orders(corporation_id)
    if not response.success():
        logger.warning(
            "ESI corporation orders failed for %s via %s: %s",
            corporation_id,
            director.character_id,
            response.response_code,
        )
        return OrderSyncResult(status=OrderSyncStatus.FAILED)

    return _replace_orders_from_esi(
        raw_orders=response.results() or [],
        owner_for=lambda raw: (
            int(raw["issued_by"]) if raw.get("issued_by") is not None else None
        ),
        corporation_id=corporation_id,
        delete_queryset=EveMarketAttributedOrder.objects.filter(
            corporation_id=corporation_id,
        ),
    )


def character_ids_for_attributed_order_sync() -> list[int]:
    """Personal sync targets: Market-scoped characters of eligible tribe members."""
    return market_scope_character_ids(
        user_ids=eligible_market_operator_user_ids()
    )


def allied_corporation_ids_for_order_sync() -> list[int]:
    return list(
        EveCorporation.objects.filter(
            alliance__name__in=ALLIED_ALLIANCE_NAMES
        ).values_list("corporation_id", flat=True)
    )
