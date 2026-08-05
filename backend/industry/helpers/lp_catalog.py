"""LP store catalog type-id helpers (kept free of market.tasks imports)."""

from __future__ import annotations

import logging
from typing import Dict, Iterable, List, Set

from django.db.models import Q
from eveuniverse.models import EveType

from industry.helpers.blueprint_efficiency import is_faction_navy_hull
from industry.helpers.type_breakdown import get_blueprint_or_reaction_type_id
from industry.models import (
    IndustryLpStoreOffer,
    IndustryLpStoreOfferRequiredItem,
    IndustryProduct,
)

logger = logging.getLogger(__name__)

# Eve SDE: Criminal Tags (Angel/Blood/Domination/Navy tags, etc.)
CRIMINAL_TAGS_GROUP_ID = 370

# Eve SDE: Permanent / time-limited ship SKINs (category "SKINs").
SKINS_CATEGORY_ID = 91

# Duplicated from product_unit_cost to avoid loyalty_store circular imports.
TALWAR_FI_TYPE_ID = 91858
TALWAR_FI_BPC_TYPE_ID = 91862


def lp_catalog_type_ids() -> List[int]:
    """Distinct type IDs from LP store offers and required items."""
    offer_types = IndustryLpStoreOffer.objects.values_list(
        "type_id", flat=True
    ).distinct()
    req_types = IndustryLpStoreOfferRequiredItem.objects.values_list(
        "type_id", flat=True
    ).distinct()
    return sorted({int(t) for t in offer_types} | {int(t) for t in req_types})


def navy_bpc_to_hull_type_ids() -> Dict[int, int]:
    """Map faction navy BPC type_id → tradeable hull type_id."""
    mapping: Dict[int, int] = {TALWAR_FI_BPC_TYPE_ID: TALWAR_FI_TYPE_ID}
    products = IndustryProduct.objects.select_related(
        "eve_type", "eve_type__eve_group", "eve_type__eve_group__eve_category"
    ).filter(eve_type_id__isnull=False)
    for product in products:
        eve_type = product.eve_type
        if not is_faction_navy_hull(eve_type):
            continue
        bpc_id = get_blueprint_or_reaction_type_id(eve_type)
        if bpc_id is None:
            continue
        mapping[int(bpc_id)] = int(eve_type.id)
    return mapping


def expand_with_navy_hull_type_ids(type_ids: Iterable[int]) -> Set[int]:
    """
    Add mapped navy hulls when a BPC type is present.

    LP offer volume/price columns look up the hull for BPC offers, so Forge
    history must cover those hulls even when only the BPC is in the catalog.
    """
    ids = {int(t) for t in type_ids if int(t) > 0}
    if not ids:
        return set()
    bpc_map = navy_bpc_to_hull_type_ids()
    for tid in list(ids):
        hull_id = bpc_map.get(tid)
        if hull_id is not None:
            ids.add(int(hull_id))
    return ids


def lp_market_history_type_ids() -> List[int]:
    """Type IDs that need Forge market history for LP store economics."""
    return sorted(expand_with_navy_hull_type_ids(lp_catalog_type_ids()))


def ensure_eve_types(type_ids: Iterable[int]) -> Set[int]:
    """
    Load missing EveType rows from ESI.

    Batch-checks local existence, then calls get_or_create_esi only for
    missing IDs (no admin N+1). Returns the set of type IDs that were
    fetched (or attempted). Failures are logged and skipped so one bad
    type does not break sync / economics.
    """
    unique = sorted({int(t) for t in type_ids if int(t) > 0})
    if not unique:
        return set()
    existing = set(
        EveType.objects.filter(id__in=unique).values_list("id", flat=True)
    )
    missing = [tid for tid in unique if tid not in existing]
    fetched: Set[int] = set()
    for type_id in missing:
        try:
            EveType.objects.get_or_create_esi(id=type_id)
            fetched.add(type_id)
        except Exception:  # noqa: BLE001 — ESI / SDE edge cases
            logger.warning(
                "Failed to ensure EveType %s for LP catalog",
                type_id,
                exc_info=True,
            )
    if fetched:
        logger.info(
            "Loaded %s missing EveType(s) for LP catalog", len(fetched)
        )
    return fetched


def tag_type_ids() -> List[int]:
    """
    EveType IDs that are LP-store tags / faction insignias.

    Matches Criminal Tags group, names ending '* Tag', or names containing
    'Insignia' (Imperial/Caldari/Gallente/Minmatar navy rank insignias used
    as LP required items).
    """
    return list(
        EveType.objects.filter(
            Q(eve_group_id=CRIMINAL_TAGS_GROUP_ID)
            | Q(name__iendswith=" Tag")
            | Q(name__icontains="Insignia")
        ).values_list("id", flat=True)
    )


def supply_package_type_ids() -> List[int]:
    """EveType IDs whose name contains 'Supply Package' (militia LP crates)."""
    return list(
        EveType.objects.filter(name__icontains="Supply Package").values_list(
            "id", flat=True
        )
    )


def chip_type_ids() -> List[int]:
    """
    EveType IDs whose name contains 'Nexus Chip' (faction LP store chips).

    Matches Minmatar/Caldari/Gallente/Amarr Nexus Chips used as required
    items. Deliberately avoids a broad '* Chip' suffix, which would also
    catch Social Adaptation Chip implants.
    """
    return list(
        EveType.objects.filter(name__icontains="Nexus Chip").values_list(
            "id", flat=True
        )
    )


def skin_type_ids() -> List[int]:
    """EveType IDs in the SKINs category (permanent and timed ship skins)."""
    return list(
        EveType.objects.filter(
            eve_group__eve_category_id=SKINS_CATEGORY_ID
        ).values_list("id", flat=True)
    )
