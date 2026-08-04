"""LP store catalog type-id helpers (kept free of market.tasks imports)."""

from __future__ import annotations

from typing import List

from industry.models import (
    IndustryLpStoreOffer,
    IndustryLpStoreOfferRequiredItem,
)


def lp_catalog_type_ids() -> List[int]:
    """Distinct type IDs from LP store offers and required items."""
    offer_types = IndustryLpStoreOffer.objects.values_list(
        "type_id", flat=True
    ).distinct()
    req_types = IndustryLpStoreOfferRequiredItem.objects.values_list(
        "type_id", flat=True
    ).distinct()
    return sorted({int(t) for t in offer_types} | {int(t) for t in req_types})
