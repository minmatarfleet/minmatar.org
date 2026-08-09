"""Classify EveTypes for buyback acceptance and rate selection."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from eveuniverse.models import EveType

# Stable SDE IDs
CATEGORY_ASTEROID = 25
CATEGORY_PLANETARY_RESOURCES = 42  # P0
CATEGORY_PLANETARY_COMMODITIES = 43  # P1–P4

GROUP_ICE = 465
GROUP_KANGITE = 5086
GROUP_P1 = 1042  # Basic Commodities - Tier 1
GROUP_P2 = 1034
GROUP_P3 = 1040
GROUP_P4 = 1041
GROUP_SALVAGED_MATERIALS = 754
GROUP_ANCIENT_SALVAGE = 966

SALVAGE_GROUPS = frozenset({GROUP_SALVAGED_MATERIALS, GROUP_ANCIENT_SALVAGE})

_PI_GROUP_TO_CATEGORY = {
    GROUP_P1: "p1",
    GROUP_P2: "p2",
    GROUP_P3: "p3",
    GROUP_P4: "p4",
}


class BuybackCategory(str, Enum):
    ORE = "ore"
    P1 = "p1"
    P2 = "p2"
    P3 = "p3"
    P4 = "p4"
    SALVAGE = "salvage"
    EXCLUDED = "excluded"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Classification:
    category: BuybackCategory
    reject_reason: Optional[str] = None


def classify_eve_type(eve_type: EveType) -> Classification:
    """Map an EveType to a buyback category (ore / P1–P4 / salvage / excluded)."""
    group = getattr(eve_type, "eve_group", None)
    group_id = getattr(group, "id", None)
    category_id = getattr(group, "eve_category_id", None)
    if category_id is None and group is not None:
        cat = getattr(group, "eve_category", None)
        category_id = getattr(cat, "id", None)

    if group_id == GROUP_ICE:
        return Classification(
            BuybackCategory.EXCLUDED, reject_reason="Ice is not accepted"
        )
    if group_id == GROUP_KANGITE:
        return Classification(
            BuybackCategory.EXCLUDED,
            reject_reason="Kangite / Bulwark ores are not accepted",
        )

    if category_id == CATEGORY_ASTEROID:
        return Classification(BuybackCategory.ORE)

    pi_value = _PI_GROUP_TO_CATEGORY.get(group_id)
    if pi_value is not None:
        return Classification(BuybackCategory(pi_value))
    if category_id == CATEGORY_PLANETARY_COMMODITIES:
        return Classification(
            BuybackCategory.UNKNOWN,
            reject_reason="Unrecognized planetary commodity tier",
        )
    if category_id == CATEGORY_PLANETARY_RESOURCES:
        return Classification(
            BuybackCategory.UNKNOWN,
            reject_reason="Raw planetary resources (P0) are not accepted",
        )

    if group_id in SALVAGE_GROUPS:
        return Classification(BuybackCategory.SALVAGE)

    return Classification(
        BuybackCategory.UNKNOWN,
        reject_reason="Item type is not accepted for buyback",
    )


def resolve_types_by_name(names: list[str]) -> dict[str, EveType | None]:
    """Resolve paste names to EveType (exact match, then case-insensitive)."""
    if not names:
        return {}
    unique = list(dict.fromkeys(names))
    found: dict[str, EveType] = {}

    for eve_type in EveType.objects.filter(name__in=unique).select_related(
        "eve_group", "eve_group__eve_category"
    ):
        found[eve_type.name] = eve_type

    result: dict[str, EveType | None] = {}
    for name in unique:
        if name in found:
            result[name] = found[name]
            continue
        eve_type = (
            EveType.objects.filter(name__iexact=name)
            .select_related("eve_group", "eve_group__eve_category")
            .first()
        )
        result[name] = eve_type
    return result
