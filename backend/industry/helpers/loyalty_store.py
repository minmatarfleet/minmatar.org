"""ESI loyalty-store offers: sync full catalog into DB for conversion + planner."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Set, Tuple

from django.db import transaction
from django.db.models import Count
from django.utils import timezone

from app.celery import app
from eveonline.client import _esi_to_python, esi_provider
from eveonline.models import EveLocation
from industry.models import (
    IndustryLoyaltyPoint,
    IndustryLpStoreOffer,
    IndustryLpStoreOfferRequiredItem,
    IndustryProduct,
)
from market.helpers.pricing import JITA_REGION_ID
from market.models.history import EveMarketItemHistory

logger = logging.getLogger(__name__)

# Faction Warfare militia LP stores (bootstrap defaults).
MILITIA_CORPORATION_IDS: tuple[int, ...] = (
    1000182,  # Tribal Liberation Force
    1000179,  # 24th Imperial Crusade
    1000180,  # State Protectorate
    1000181,  # Federal Defense Union
)

MILITIA_DEFAULT_NAMES: dict[int, str] = {
    1000182: "Tribal Liberation Force",
    1000179: "24th Imperial Crusade",
    1000180: "State Protectorate",
    1000181: "Federal Defense Union",
}


@dataclass(frozen=True)
class NavyBpcCost:
    offer_id: int
    corporation_id: int
    type_id: int
    lp_cost: int
    isk_cost: int
    quantity: int
    packs: int
    isk_per_lp: float
    total_isk: int

    def to_dict(self) -> dict:
        return {
            "offer_id": self.offer_id,
            "corporation_id": self.corporation_id,
            "type_id": self.type_id,
            "lp_cost": self.lp_cost,
            "isk_cost": self.isk_cost,
            "quantity": self.quantity,
            "packs": self.packs,
            "isk_per_lp": self.isk_per_lp,
            "total_isk": self.total_isk,
        }


@dataclass(frozen=True)
class _OfferBuild:
    offer: IndustryLpStoreOffer
    required: Tuple[Tuple[int, int], ...]  # (type_id, quantity)


def is_pure_lp_isk_offer(row: dict) -> bool:
    """True for LP+ISK offers with no required items and no ak_cost (navy BPC)."""
    if not isinstance(row, dict):
        return False
    if row.get("required_items"):
        return False
    if int(row.get("ak_cost") or 0) > 0:
        return False
    lp_cost = int(row.get("lp_cost") or 0)
    isk_cost = int(row.get("isk_cost") or 0)
    return lp_cost > 0 and isk_cost > 0


def corporation_ids_to_sync() -> List[int]:
    """Active IndustryLoyaltyPoint corps, else FW militia defaults."""
    ids = list(
        IndustryLoyaltyPoint.objects.filter(is_active=True).values_list(
            "corporation_id", flat=True
        )
    )
    return [int(i) for i in ids] if ids else list(MILITIA_CORPORATION_IDS)


def default_isk_per_lp_for_corporation(corporation_id: int) -> Optional[int]:
    row = (
        IndustryLoyaltyPoint.objects.filter(
            corporation_id=int(corporation_id), is_active=True
        )
        .values_list("default_isk_per_lp", flat=True)
        .first()
    )
    return int(row) if row is not None else None


def fetch_loyalty_offers_from_esi(
    corporation_ids: Sequence[int] | None = None,
) -> List[dict]:
    """Fetch loyalty-store offers for each corporation (public ESI, no token)."""
    if corporation_ids is None:
        corporation_ids = corporation_ids_to_sync()
    offers: List[dict] = []
    for corporation_id in corporation_ids:
        try:
            rows = _esi_to_python(
                esi_provider.client.Loyalty.GetLoyaltyStoresCorporationIdOffers(
                    corporation_id=int(corporation_id)
                ).results(
                    use_etag=False
                )
            )
        except Exception as exc:
            raise ValueError(
                f"Failed to fetch ESI loyalty offers for corp "
                f"{corporation_id}: {exc}"
            ) from exc
        if not isinstance(rows, list):
            raise ValueError(
                f"Unexpected loyalty offers payload for corp "
                f"{corporation_id}: {type(rows)!r}"
            )
        for row in rows:
            if not isinstance(row, dict):
                continue
            offer = dict(row)
            offer["corporation_id"] = int(corporation_id)
            offers.append(offer)
    return offers


def _builds_from_rows(
    rows: Iterable[dict],
    *,
    now,
) -> List[_OfferBuild]:
    """Parse ESI rows into offer + required-item builds (all valid offers)."""
    builds: List[_OfferBuild] = []
    seen: Set[Tuple[int, int]] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        offer_id = int(row.get("offer_id") or 0)
        type_id = int(row.get("type_id") or 0)
        corporation_id = int(
            row.get("corporation_id") or row.get("corporationId") or 0
        )
        if offer_id <= 0 or type_id <= 0 or corporation_id <= 0:
            continue
        key = (corporation_id, offer_id)
        if key in seen:
            continue
        seen.add(key)
        quantity = max(int(row.get("quantity") or 1), 1)
        required_raw = row.get("required_items") or []
        required: list[tuple[int, int]] = []
        if isinstance(required_raw, list):
            seen_req: set[int] = set()
            for item in required_raw:
                if not isinstance(item, dict):
                    continue
                req_type = int(item.get("type_id") or 0)
                req_qty = int(item.get("quantity") or 0)
                if req_type <= 0 or req_qty <= 0 or req_type in seen_req:
                    continue
                seen_req.add(req_type)
                required.append((req_type, req_qty))
        builds.append(
            _OfferBuild(
                offer=IndustryLpStoreOffer(
                    offer_id=offer_id,
                    corporation_id=corporation_id,
                    type_id=type_id,
                    lp_cost=int(row.get("lp_cost") or 0),
                    isk_cost=int(row.get("isk_cost") or 0),
                    ak_cost=int(row.get("ak_cost") or 0),
                    quantity=quantity,
                    updated_at=now,
                ),
                required=tuple(required),
            )
        )
    return builds


def _enqueue_history_for_missing_types(type_ids: Set[int]) -> None:
    """Bootstrap Forge history for LP catalog types missing recent rows."""
    if not type_ids:
        return
    # Use send_task by name to avoid importing market.tasks (it imports us).
    baseline = EveLocation.objects.filter(price_baseline=True).first()
    region_id = (
        baseline.region_id
        if baseline and baseline.region_id
        else JITA_REGION_ID
    )
    existing = set(
        EveMarketItemHistory.objects.filter(
            region_id=region_id,
            item_id__in=type_ids,
        )
        .values_list("item_id", flat=True)
        .distinct()
    )
    missing = sorted(tid for tid in type_ids if tid not in existing)
    for type_id in missing:
        app.send_task(
            "market.tasks.fetch_market_item_history_for_type",
            args=[type_id],
            queue="market",
        )
    if missing:
        logger.info(
            "Enqueued Forge history bootstrap for %s LP catalog type(s)",
            len(missing),
        )


def sync_loyalty_store_offers(
    corporation_ids: Sequence[int] | None = None,
    *,
    offers: Optional[Iterable[dict]] = None,
    replace_all: bool = False,
    enqueue_history: bool = True,
) -> int:
    """
    Pull ESI loyalty offers (or use ``offers``) and upsert the local cache.

    Stores the full catalog including required-item offers. Identity is
    (corporation_id, offer_id). By default replaces offers only for the
    synced corporation IDs. Returns the number of offers stored.
    """
    if corporation_ids is None:
        corporation_ids = corporation_ids_to_sync()
    corp_ids = [int(c) for c in corporation_ids]
    rows = (
        list(offers)
        if offers is not None
        else fetch_loyalty_offers_from_esi(corp_ids)
    )
    now = timezone.now()
    builds = _builds_from_rows(rows, now=now)
    with transaction.atomic():
        if replace_all:
            IndustryLpStoreOffer.objects.all().delete()
        else:
            IndustryLpStoreOffer.objects.filter(
                corporation_id__in=corp_ids
            ).delete()
        IndustryLpStoreOffer.objects.bulk_create([b.offer for b in builds])
        # Re-query PKs: bulk_create does not reliably set pk on all backends.
        key_to_pk = {
            (int(o.corporation_id), int(o.offer_id)): int(o.pk)
            for o in IndustryLpStoreOffer.objects.filter(
                corporation_id__in=corp_ids
            ).only("id", "corporation_id", "offer_id")
        }
        req_rows: List[IndustryLpStoreOfferRequiredItem] = []
        for build in builds:
            offer_pk = key_to_pk.get(
                (build.offer.corporation_id, build.offer.offer_id)
            )
            if offer_pk is None:
                continue
            for req_type_id, req_qty in build.required:
                req_rows.append(
                    IndustryLpStoreOfferRequiredItem(
                        offer_id=offer_pk,
                        type_id=req_type_id,
                        quantity=req_qty,
                    )
                )
        if req_rows:
            IndustryLpStoreOfferRequiredItem.objects.bulk_create(req_rows)
    catalog_types: Set[int] = {b.offer.type_id for b in builds}
    for build in builds:
        catalog_types.update(tid for tid, _ in build.required)
    if enqueue_history:
        _enqueue_history_for_missing_types(catalog_types)
    logger.info(
        "Synced %s loyalty-store offer(s) for corp(s) %s",
        len(builds),
        corp_ids,
    )
    return len(builds)


def _pure_offers_for_type(type_id: int) -> List[IndustryLpStoreOffer]:
    """Persisted pure LP+ISK offers for a type (no required items, no ak)."""
    return list(
        IndustryLpStoreOffer.objects.filter(
            type_id=type_id,
            ak_cost=0,
            lp_cost__gt=0,
            isk_cost__gt=0,
        )
        .annotate(req_count=Count("required_items"))
        .filter(req_count=0)
    )


def ensure_loyalty_store_offers_for_blueprint(
    blueprint_type_id: int,
) -> Optional[IndustryLpStoreOffer]:
    """
    Ensure a pure offer exists for ``blueprint_type_id``; sync from ESI if missing.
    """
    blueprint_type_id = int(blueprint_type_id)
    existing = _pure_offers_for_type(blueprint_type_id)
    if existing:
        return existing[0]
    logger.info(
        "No pure LP store offer for blueprint type %s; syncing from ESI",
        blueprint_type_id,
    )
    sync_loyalty_store_offers()
    existing = _pure_offers_for_type(blueprint_type_id)
    return existing[0] if existing else None


def ensure_loyalty_store_offers_for_product(product_id: int) -> int:
    """
    When a navy/faction IndustryProduct is saved, refresh LP offers if needed.
    """
    from industry.helpers.blueprint_efficiency import (  # pylint: disable=import-outside-toplevel
        is_faction_navy_hull,
    )
    from industry.helpers.type_breakdown import (  # pylint: disable=import-outside-toplevel
        get_blueprint_or_reaction_type_id,
    )

    product = (
        IndustryProduct.objects.select_related("eve_type")
        .filter(pk=product_id)
        .first()
    )
    if product is None or product.eve_type_id is None:
        return 0
    if not is_faction_navy_hull(product.eve_type):
        return 0
    blueprint_type_id = get_blueprint_or_reaction_type_id(product.eve_type)
    if blueprint_type_id is None:
        return 0
    if _pure_offers_for_type(blueprint_type_id):
        return 0
    return sync_loyalty_store_offers()


def get_offer_for_blueprint_type(
    type_id: int,
    *,
    isk_per_lp: float = 1.0,
) -> Optional[IndustryLpStoreOffer]:
    """
    Best persisted pure offer for a blueprint type_id.

    Reads DB first; syncs from ESI only when that type (or the table) is missing.
    """
    type_id = int(type_id)
    rows = _pure_offers_for_type(type_id)
    if not rows:
        ensure_loyalty_store_offers_for_blueprint(type_id)
        rows = _pure_offers_for_type(type_id)
    if not rows:
        return None

    rate = max(float(isk_per_lp), 0.0)

    def pack_cost(row: IndustryLpStoreOffer) -> float:
        qty = max(int(row.quantity), 1)
        return (row.lp_cost * rate + row.isk_cost) / qty

    return min(rows, key=pack_cost)


def navy_bpc_cost_for_plan(
    blueprint_type_id: int,
    hull_quantity: int,
    isk_per_lp: float,
) -> Optional[NavyBpcCost]:
    """
    Cost to acquire enough navy BPCs for ``hull_quantity`` hulls at isk/LP.
    """
    if hull_quantity < 1 or isk_per_lp is None or float(isk_per_lp) <= 0:
        return None
    offer = get_offer_for_blueprint_type(
        blueprint_type_id, isk_per_lp=float(isk_per_lp)
    )
    if offer is None:
        return None
    qty = max(int(offer.quantity), 1)
    packs = int(math.ceil(hull_quantity / qty))
    rate = float(isk_per_lp)
    per_pack = int(round(offer.lp_cost * rate + offer.isk_cost))
    return NavyBpcCost(
        offer_id=int(offer.offer_id),
        corporation_id=int(offer.corporation_id),
        type_id=int(offer.type_id),
        lp_cost=int(offer.lp_cost),
        isk_cost=int(offer.isk_cost),
        quantity=qty,
        packs=packs,
        isk_per_lp=rate,
        total_isk=packs * per_pack,
    )


def resolve_isk_per_lp(
    *,
    requested: Optional[float],
    corporation_id: Optional[int] = None,
) -> Optional[float]:
    """
    Prefer explicit request rate; else IndustryLoyaltyPoint default for corp.
    """
    if requested is not None and float(requested) > 0:
        return float(requested)
    if corporation_id is not None:
        default = default_isk_per_lp_for_corporation(int(corporation_id))
        if default is not None and default > 0:
            return float(default)
    return None


def lp_catalog_type_ids() -> List[int]:
    """Distinct type IDs from LP store offers and required items."""
    offer_types = IndustryLpStoreOffer.objects.values_list(
        "type_id", flat=True
    ).distinct()
    req_types = IndustryLpStoreOfferRequiredItem.objects.values_list(
        "type_id", flat=True
    ).distinct()
    return sorted({int(t) for t in offer_types} | {int(t) for t in req_types})
