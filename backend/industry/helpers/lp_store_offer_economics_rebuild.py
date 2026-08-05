"""Rebuild persisted LP store offer economics from local caches (no ESI)."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional, Set

from django.utils import timezone

from eveonline.helpers.db_sync import replace_with_bulk_create
from industry.helpers.lp_catalog import (
    chip_type_ids,
    skin_type_ids,
    supply_package_type_ids,
    tag_type_ids,
)
from industry.helpers.lp_store_economics import (
    LpStoreOfferEconomics,
    display_type_name,
    offer_economics_for_queryset,
    offer_is_below_set_lp_price,
    tracked_corporation_ids,
)
from industry.helpers.lp_store_useless import (
    CurrencyPeerStats,
    offer_is_useless,
    peer_stats_by_corporation,
)
from industry.models import (
    IndustryLpStoreOffer,
    IndustryLpStoreOfferEconomics,
    IndustryLpStoreOfferRequiredItem,
)

logger = logging.getLogger(__name__)


def _offer_pks_involving_types(type_ids: Set[int]) -> Set[int]:
    if not type_ids:
        return set()
    req_pks = IndustryLpStoreOfferRequiredItem.objects.filter(
        type_id__in=type_ids
    ).values_list("offer_id", flat=True)
    output_pks = IndustryLpStoreOffer.objects.filter(
        type_id__in=type_ids
    ).values_list("pk", flat=True)
    return set(req_pks) | set(output_pks)


def economics_row_from_offer(
    offer: IndustryLpStoreOffer,
    econ: LpStoreOfferEconomics,
    *,
    peer: Optional[CurrencyPeerStats],
    tag_pks: Set[int],
    package_pks: Set[int],
    chip_pks: Set[int],
    skin_pks: Set[int],
    rebuilt_at: datetime,
) -> IndustryLpStoreOfferEconomics:
    """Build one snapshot row from an offer + live economics dataclass."""
    return IndustryLpStoreOfferEconomics(
        offer_id=offer.pk,
        esi_offer_id=int(offer.offer_id),
        corporation_id=int(offer.corporation_id),
        type_id=int(econ.type_id),
        type_name=display_type_name(econ)[:255],
        currency_name=(econ.currency_name or "")[:128],
        kind=(econ.kind or "")[:32],
        lp_cost=int(offer.lp_cost),
        isk_cost=int(offer.isk_cost),
        ak_cost=int(offer.ak_cost),
        quantity=int(offer.quantity),
        required_items_summary=(econ.required_items_summary or "")[:512],
        other_cost=econ.other_cost,
        jita_sell=econ.jita_sell,
        jita_buy=econ.jita_buy,
        jita_avg_7d=econ.jita_avg_7d,
        conversion_isk_per_lp_sell=econ.conversion_isk_per_lp_sell,
        conversion_isk_per_lp_buy=econ.conversion_isk_per_lp_buy,
        conversion_isk_per_lp_avg_7d=econ.conversion_isk_per_lp_avg_7d,
        volume_1d=econ.volume_1d,
        volume_7d=econ.volume_7d,
        volume_30d=econ.volume_30d,
        involves_tag=offer.pk in tag_pks,
        involves_supply_package=offer.pk in package_pks,
        involves_chip=offer.pk in chip_pks,
        involves_skin=offer.pk in skin_pks,
        is_useless=offer_is_useless(econ, peer),
        is_below_set_lp_price=offer_is_below_set_lp_price(econ),
        is_below_set_lp_price_buy=offer_is_below_set_lp_price(
            econ, side="buy"
        ),
        is_below_set_lp_price_avg_7d=offer_is_below_set_lp_price(
            econ, side="avg_7d"
        ),
        offer_updated_at=offer.updated_at,
        rebuilt_at=rebuilt_at,
    )


def rebuild_lp_store_offer_economics() -> int:
    """
    Recompute economics for tracked LP store offers and replace the snapshot.

    Uses cached IndustryLpStoreOffer rows plus local Jita/Forge price data —
    no ESI. Returns the number of snapshot rows written.
    """
    corp_ids = tracked_corporation_ids()
    if not corp_ids:
        count = replace_with_bulk_create(
            delete_queryset=IndustryLpStoreOfferEconomics.objects.all(),
            instances=[],
        )
        logger.info("LP offer economics rebuild: no tracked corps, cleared")
        return count

    offers = list(
        IndustryLpStoreOffer.objects.filter(corporation_id__in=corp_ids)
    )
    economics = offer_economics_for_queryset(offers)
    peers = peer_stats_by_corporation(economics)
    tag_pks = _offer_pks_involving_types(set(tag_type_ids()))
    package_pks = _offer_pks_involving_types(set(supply_package_type_ids()))
    chip_pks = _offer_pks_involving_types(set(chip_type_ids()))
    skin_pks = _offer_pks_involving_types(set(skin_type_ids()))
    now = timezone.now()

    rows: List[IndustryLpStoreOfferEconomics] = []
    for offer in offers:
        econ = economics.get(offer.pk)
        if econ is None:
            continue
        rows.append(
            economics_row_from_offer(
                offer,
                econ,
                peer=peers.get(int(econ.corporation_id)),
                tag_pks=tag_pks,
                package_pks=package_pks,
                chip_pks=chip_pks,
                skin_pks=skin_pks,
                rebuilt_at=now,
            )
        )

    count = replace_with_bulk_create(
        delete_queryset=IndustryLpStoreOfferEconomics.objects.all(),
        instances=rows,
    )
    logger.info(
        "LP offer economics rebuild: wrote %s row(s) for %s offer(s)",
        count,
        len(offers),
    )
    return count


__all__ = [
    "economics_row_from_offer",
    "rebuild_lp_store_offer_economics",
]
