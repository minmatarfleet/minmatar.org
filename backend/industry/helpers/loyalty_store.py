"""ESI loyalty-store offers: sync pure LP+ISK rows into DB for the planner."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence

from django.db import transaction
from django.utils import timezone

from eveonline.client import _esi_to_python, esi_provider
from industry.models import (
    IndustryLoyaltyPoint,
    IndustryLpStoreOffer,
    IndustryProduct,
)

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


def is_pure_lp_isk_offer(row: dict) -> bool:
    """True for LP+ISK offers with no required items (navy BPC path)."""
    if not isinstance(row, dict):
        return False
    if row.get("required_items"):
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


def _instances_from_rows(
    rows: Iterable[dict],
    *,
    now,
) -> List[IndustryLpStoreOffer]:
    instances: List[IndustryLpStoreOffer] = []
    seen_offer_ids: set[int] = set()
    for row in rows:
        if not is_pure_lp_isk_offer(row):
            continue
        offer_id = int(row.get("offer_id") or 0)
        type_id = int(row.get("type_id") or 0)
        if offer_id <= 0 or type_id <= 0 or offer_id in seen_offer_ids:
            continue
        seen_offer_ids.add(offer_id)
        quantity = max(int(row.get("quantity") or 1), 1)
        instances.append(
            IndustryLpStoreOffer(
                offer_id=offer_id,
                corporation_id=int(
                    row.get("corporation_id") or row.get("corporationId") or 0
                ),
                type_id=type_id,
                lp_cost=int(row["lp_cost"]),
                isk_cost=int(row["isk_cost"]),
                quantity=quantity,
                updated_at=now,
            )
        )
    return instances


def sync_loyalty_store_offers(
    corporation_ids: Sequence[int] | None = None,
    *,
    offers: Optional[Iterable[dict]] = None,
    replace_all: bool = False,
) -> int:
    """
    Pull ESI loyalty offers (or use ``offers``) and upsert the local cache.

    Only pure LP+ISK rows (no required items) are stored.
    By default replaces offers only for the synced corporation IDs.
    Returns the number of offers stored in this sync.
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
    instances = _instances_from_rows(rows, now=now)
    with transaction.atomic():
        if replace_all:
            IndustryLpStoreOffer.objects.all().delete()
        else:
            IndustryLpStoreOffer.objects.filter(
                corporation_id__in=corp_ids
            ).delete()
        IndustryLpStoreOffer.objects.bulk_create(instances)
    logger.info(
        "Synced %s pure LP+ISK loyalty-store offer(s) for corp(s) %s",
        len(instances),
        corp_ids,
    )
    return len(instances)


def ensure_loyalty_store_offers_for_blueprint(
    blueprint_type_id: int,
) -> Optional[IndustryLpStoreOffer]:
    """
    Ensure a pure offer exists for ``blueprint_type_id``; sync from ESI if missing.
    """
    blueprint_type_id = int(blueprint_type_id)
    existing = IndustryLpStoreOffer.objects.filter(
        type_id=blueprint_type_id
    ).first()
    if existing is not None:
        return existing
    logger.info(
        "No LP store offer for blueprint type %s; syncing from ESI",
        blueprint_type_id,
    )
    sync_loyalty_store_offers()
    return IndustryLpStoreOffer.objects.filter(
        type_id=blueprint_type_id
    ).first()


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
    if IndustryLpStoreOffer.objects.filter(type_id=blueprint_type_id).exists():
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
    rows = list(IndustryLpStoreOffer.objects.filter(type_id=type_id))
    if not rows:
        ensure_loyalty_store_offers_for_blueprint(type_id)
        rows = list(IndustryLpStoreOffer.objects.filter(type_id=type_id))
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
