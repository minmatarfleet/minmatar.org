"""ESI loyalty-store offers: sync pure LP+ISK rows into DB for the planner."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence

from django.utils import timezone

from eveonline.client import _esi_to_python, esi_provider
from eveonline.helpers.db_sync import replace_with_bulk_create
from industry.models import IndustryLpStoreOffer

logger = logging.getLogger(__name__)

# Faction Warfare militia LP stores.
MILITIA_CORPORATION_IDS: tuple[int, ...] = (
    1000182,  # Tribal Liberation Force
    1000179,  # 24th Imperial Crusade
    1000180,  # State Protectorate
    1000181,  # Federal Defense Union
)


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


def fetch_loyalty_offers_from_esi(
    corporation_ids: Sequence[int] = MILITIA_CORPORATION_IDS,
) -> List[dict]:
    """
    Fetch loyalty-store offers for each corporation (public ESI, no token).
    """
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


def sync_loyalty_store_offers(
    corporation_ids: Sequence[int] = MILITIA_CORPORATION_IDS,
    *,
    offers: Optional[Iterable[dict]] = None,
) -> int:
    """
    Pull ESI loyalty offers (or use ``offers``) and replace the local cache.

    Only pure LP+ISK rows (no required items) are stored.
    Returns the number of offers stored.
    """
    rows = (
        list(offers)
        if offers is not None
        else fetch_loyalty_offers_from_esi(corporation_ids)
    )
    now = timezone.now()
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
    count = replace_with_bulk_create(
        delete_queryset=IndustryLpStoreOffer.objects.all(),
        instances=instances,
    )
    logger.info("Synced %s pure LP+ISK loyalty-store offer(s)", count)
    return count


def get_offer_for_blueprint_type(
    type_id: int,
    *,
    isk_per_lp: float = 1.0,
) -> Optional[IndustryLpStoreOffer]:
    """
    Best persisted pure offer for a blueprint type_id.

    Reads DB only. If the table is empty (fresh deploy), runs a one-shot
    ESI sync then re-reads. Steady-state planner traffic does not call ESI.
    """
    type_id = int(type_id)
    if not IndustryLpStoreOffer.objects.exists():
        logger.info("No cached LP store offers; syncing from ESI once")
        sync_loyalty_store_offers()

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
