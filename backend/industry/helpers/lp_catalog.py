"""LP store catalog type-id helpers (kept free of market.tasks imports)."""

from __future__ import annotations

import logging
from typing import Iterable, List, Set

from django.db.models import Q
from eveuniverse.models import EveType

from industry.models import (
    IndustryLpStoreOffer,
    IndustryLpStoreOfferRequiredItem,
)

logger = logging.getLogger(__name__)

# Eve SDE: Criminal Tags (Angel/Blood/Domination/Navy tags, etc.)
CRIMINAL_TAGS_GROUP_ID = 370


def lp_catalog_type_ids() -> List[int]:
    """Distinct type IDs from LP store offers and required items."""
    offer_types = IndustryLpStoreOffer.objects.values_list(
        "type_id", flat=True
    ).distinct()
    req_types = IndustryLpStoreOfferRequiredItem.objects.values_list(
        "type_id", flat=True
    ).distinct()
    return sorted({int(t) for t in offer_types} | {int(t) for t in req_types})


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
    EveType IDs that are LP-store tags (Criminal Tags group or '* Tag' name).
    """
    return list(
        EveType.objects.filter(
            Q(eve_group_id=CRIMINAL_TAGS_GROUP_ID) | Q(name__iendswith=" Tag")
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
