"""Classify EveTypes for Market Ops gap filters (type + variant)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from eveuniverse.models import (
    EveType,
    EveTypeDogmaAttribute,
    EveTypeDogmaEffect,
)

# Dogma attribute / effect IDs from SDE (stable).
DOGMA_META_GROUP_ID = 1692
DOGMA_TECH_LEVEL_ID = 422
META_GROUP_T2 = 2.0
META_GROUP_STORYLINE = 3.0  # named / storyline
META_GROUP_FACTION = 4.0
META_GROUP_OFFICER = 5.0
META_GROUP_DEADSPACE = 6.0  # A/B/C/X-Type

EFFECT_HI_POWER = 12
EFFECT_LO_POWER = 11
EFFECT_MED_POWER = 13
EFFECT_RIG_SLOT = 2663

CATEGORY_SHIP = "Ship"
CATEGORY_MODULE = "Module"
CATEGORY_SUBSYSTEM = "Subsystem"
CATEGORY_DRONE = "Drone"

STRUCTURAL_CATEGORIES = frozenset(
    {CATEGORY_SHIP, CATEGORY_MODULE, CATEGORY_SUBSYSTEM}
)

ITEM_TYPE_HULL = "hull"
ITEM_TYPE_HIGH_SLOT = "high_slot"
ITEM_TYPE_MEDIUM_SLOT = "medium_slot"
ITEM_TYPE_LOW_SLOT = "low_slot"
ITEM_TYPE_CONSUMABLE = "consumable"
ITEM_TYPE_DRONE = "drone"
ITEM_TYPE_RIG = "rig"
ITEM_TYPE_OTHER = "other"

ITEM_TYPES = frozenset(
    {
        ITEM_TYPE_HULL,
        ITEM_TYPE_HIGH_SLOT,
        ITEM_TYPE_MEDIUM_SLOT,
        ITEM_TYPE_LOW_SLOT,
        ITEM_TYPE_CONSUMABLE,
        ITEM_TYPE_DRONE,
        ITEM_TYPE_RIG,
        ITEM_TYPE_OTHER,
    }
)

ITEM_VARIANT_T1 = "t1"
ITEM_VARIANT_T2 = "t2"
ITEM_VARIANT_FACTION = "faction"
ITEM_VARIANT_DEADSPACE = "deadspace"
ITEM_VARIANT_OTHER = "other"

ITEM_VARIANTS = frozenset(
    {
        ITEM_VARIANT_T1,
        ITEM_VARIANT_T2,
        ITEM_VARIANT_FACTION,
        ITEM_VARIANT_DEADSPACE,
        ITEM_VARIANT_OTHER,
    }
)

_NAVY_NAME_SUFFIXES = (
    "Navy Issue",
    "Fleet Issue",
)

_SLOT_BY_EFFECT = {
    EFFECT_HI_POWER: ITEM_TYPE_HIGH_SLOT,
    EFFECT_MED_POWER: ITEM_TYPE_MEDIUM_SLOT,
    EFFECT_LO_POWER: ITEM_TYPE_LOW_SLOT,
    EFFECT_RIG_SLOT: ITEM_TYPE_RIG,
}


@dataclass(frozen=True)
class ItemClassification:
    item_type: str
    item_variant: str


def _is_faction_name(name: str | None) -> bool:
    text = (name or "").strip()
    return any(text.endswith(suffix) for suffix in _NAVY_NAME_SUFFIXES)


def _classify_variant(
    *,
    name: str | None,
    meta: float | None,
    tech: float | None,
) -> str:
    if meta == META_GROUP_FACTION or _is_faction_name(name):
        return ITEM_VARIANT_FACTION
    if meta == META_GROUP_DEADSPACE:
        return ITEM_VARIANT_DEADSPACE
    if tech == 2.0 or meta == META_GROUP_T2:
        return ITEM_VARIANT_T2
    # Officer + named/storyline before the T1 catch-all (tech is often still 1).
    if meta in (META_GROUP_STORYLINE, META_GROUP_OFFICER):
        return ITEM_VARIANT_OTHER
    if meta is None or meta in (0.0, 1.0) or tech in (None, 1.0):
        return ITEM_VARIANT_T1
    return ITEM_VARIANT_OTHER


def classify_items(type_ids: Iterable[int]) -> dict[int, ItemClassification]:
    """
    Bulk-classify EveType IDs into ops gap item_type + item_variant.

    Missing / unknown IDs are omitted from the result.
    """
    ids = list({int(type_id) for type_id in type_ids})
    if not ids:
        return {}

    types = {
        row["id"]: row
        for row in EveType.objects.filter(id__in=ids).values(
            "id",
            "name",
            "eve_group__eve_category__name",
        )
    }

    meta_by_type: dict[int, float] = {}
    tech_by_type: dict[int, float] = {}
    for row in EveTypeDogmaAttribute.objects.filter(
        eve_type_id__in=ids,
        eve_dogma_attribute_id__in=(DOGMA_META_GROUP_ID, DOGMA_TECH_LEVEL_ID),
    ).values("eve_type_id", "eve_dogma_attribute_id", "value"):
        type_id = row["eve_type_id"]
        value = float(row["value"])
        if row["eve_dogma_attribute_id"] == DOGMA_META_GROUP_ID:
            meta_by_type[type_id] = value
        else:
            tech_by_type[type_id] = value

    slot_by_type: dict[int, str] = {}
    for row in EveTypeDogmaEffect.objects.filter(
        eve_type_id__in=ids,
        eve_dogma_effect_id__in=_SLOT_BY_EFFECT.keys(),
    ).values("eve_type_id", "eve_dogma_effect_id"):
        type_id = row["eve_type_id"]
        effect_id = row["eve_dogma_effect_id"]
        # Prefer rig over slot power if both somehow present.
        if effect_id == EFFECT_RIG_SLOT:
            slot_by_type[type_id] = ITEM_TYPE_RIG
        elif type_id not in slot_by_type:
            slot_by_type[type_id] = _SLOT_BY_EFFECT[effect_id]

    classified: dict[int, ItemClassification] = {}
    for type_id, row in types.items():
        category = row["eve_group__eve_category__name"] or ""
        name = row["name"]
        variant = _classify_variant(
            name=name,
            meta=meta_by_type.get(type_id),
            tech=tech_by_type.get(type_id),
        )

        if category == CATEGORY_SHIP:
            item_type = ITEM_TYPE_HULL
        elif category == CATEGORY_DRONE:
            item_type = ITEM_TYPE_DRONE
        elif category == CATEGORY_MODULE:
            item_type = slot_by_type.get(type_id, ITEM_TYPE_OTHER)
        elif category not in STRUCTURAL_CATEGORIES:
            item_type = ITEM_TYPE_CONSUMABLE
        else:
            item_type = ITEM_TYPE_OTHER

        classified[type_id] = ItemClassification(
            item_type=item_type,
            item_variant=variant,
        )

    return classified


def classify_item_types(type_ids: Iterable[int]) -> dict[int, str]:
    """Back-compat: type-only map (prefer classify_items)."""
    return {
        type_id: row.item_type
        for type_id, row in classify_items(type_ids).items()
    }
