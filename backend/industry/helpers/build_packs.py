"""Match outstanding BUILD alliance supply contracts to an industry order line.

BUILD publishes BPC and material packs as corporation contracts assigned to the
alliance. They are not fitting-matched (so they never reach ``EveMarketContract``
and the ops pages) and ESI stores them with ``availability="personal"``, so
``assignee_id`` is the only reliable filter. Contract *items* are not synced, so
matching is a title heuristic — this is informational copy in the claim dialog,
not an authoritative stock list.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from eveonline.models import EveCorporationContract, EveLocation

BUILD_ALLIANCE_ID = 99012009

MATERIAL_PACK_MARKERS = ("material pack", "mineral pack")


@dataclass(frozen=True)
class BuildPack:
    """One or more identical outstanding pack contracts, collapsed."""

    title: str
    count: int
    price: Decimal | None
    location_name: str | None


def group_name_tokens(eve_type) -> set[str]:
    """Group name plus its last word.

    Pack titles say "Battlecruiser Material Pack" while the Eve group is
    "Combat Battlecruiser", so the bare noun has to match too.
    """
    group = getattr(eve_type, "eve_group", None)
    name = (getattr(group, "name", "") or "").casefold().strip()
    if not name:
        return set()
    return {name, name.rsplit(" ", 1)[-1]}


def title_matches_item(title: str, eve_type) -> bool:
    """True when a contract title reads as a pack for this hull.

    BPC packs match on the hull name; material packs match on the hull's group.
    The hull check is deliberately one-directional: an order for ``Typhoon``
    matches a "Typhoon Fleet Issue BPC" pack, but an order for the Fleet Issue
    does not match a plain "Typhoon BPCs" pack. Over-listing is the safer error
    for an informational panel.
    """
    folded = (title or "").casefold()
    if not folded:
        return False
    hull = (getattr(eve_type, "name", "") or "").casefold()
    if hull and hull in folded and "bpc" in folded:
        return True
    if any(marker in folded for marker in MATERIAL_PACK_MARKERS):
        return any(token in folded for token in group_name_tokens(eve_type))
    return False


def match_build_packs_for_item(order_item) -> list[BuildPack]:
    """Outstanding BUILD packs matching an order line, identical rows collapsed."""
    eve_type = order_item.eve_type
    matched = [
        contract
        for contract in EveCorporationContract.objects.filter(
            assignee_id=BUILD_ALLIANCE_ID,
            type="item_exchange",
            status="outstanding",
        )
        if title_matches_item(contract.title, eve_type)
    ]
    if not matched:
        return []

    location_ids = {
        contract.start_location_id
        for contract in matched
        if contract.start_location_id
    }
    location_names = dict(
        EveLocation.objects.filter(location_id__in=location_ids).values_list(
            "location_id", "location_name"
        )
    )

    counts: dict[tuple, int] = {}
    for contract in matched:
        key = (contract.title, contract.price, contract.start_location_id)
        counts[key] = counts.get(key, 0) + 1

    packs = [
        BuildPack(
            title=title,
            count=count,
            price=price,
            location_name=location_names.get(location_id),
        )
        for (title, price, location_id), count in counts.items()
    ]
    packs.sort(key=lambda pack: (pack.title.casefold(), pack.price or 0))
    return packs
