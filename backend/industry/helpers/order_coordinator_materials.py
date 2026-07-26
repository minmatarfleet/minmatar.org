"""
Mineral / PI supply options for industry order coordinators.

Uses fixed catalogs (basic minerals + navy-hull PI) so volunteering does not
require a per-order BOM / plan_build pass.
"""

from __future__ import annotations

from typing import List, Optional, Sequence, Set, Tuple

from eveuniverse.models import EveType

from industry.models import IndustryOrder

# Standard minerals (no Morphite — uncommon for navy T1/FW hulls).
BASIC_MINERAL_TYPE_IDS: Tuple[int, ...] = (
    34,  # Tritanium
    35,  # Pyerite
    36,  # Mexallon
    37,  # Isogen
    38,  # Nocxium
    39,  # Zydrine
    40,  # Megacyte
)

# Key PI used on navy / FW hull recipes (P0 + common processed commodities).
NAVY_HULL_PI_TYPE_IDS: Tuple[int, ...] = (
    16634,  # Atmospheric Gases
    9832,  # Coolant
    44,  # Enriched Uranium
    16635,  # Evaporite Deposits
    16633,  # Hydrocarbons
    3689,  # Mechanical Parts
    2463,  # Nanites
    3683,  # Oxygen
    9848,  # Robotics
    16636,  # Silicates
    2312,  # Supertensile Plastics
    2319,  # Test Cultures
    3775,  # Viral Agent
)


def basic_mineral_type_ids() -> Set[int]:
    return set(BASIC_MINERAL_TYPE_IDS)


def navy_hull_pi_type_ids() -> Set[int]:
    return set(NAVY_HULL_PI_TYPE_IDS)


def _types_for_ids(type_ids: Sequence[int]) -> List[EveType]:
    if not type_ids:
        return []
    return list(EveType.objects.filter(id__in=type_ids).order_by("name"))


def order_mineral_type_ids(
    order: Optional[IndustryOrder] = None,
) -> Set[int]:
    """Eve type IDs allowed for mineral coordinators (order-independent)."""
    del order  # catalog is fixed; signature kept for call-site compatibility
    return basic_mineral_type_ids()


def order_pi_type_ids(order: Optional[IndustryOrder] = None) -> Set[int]:
    """Eve type IDs allowed for PI coordinators (order-independent)."""
    del order
    return navy_hull_pi_type_ids()


def order_material_options(
    order: Optional[IndustryOrder] = None,
    *,
    kind: str,
) -> List[EveType]:
    """
    Sorted EveType list for coordinator checkboxes.

    kind: ``mineral`` or ``pi``.
    """
    del order
    if kind == "mineral":
        return _types_for_ids(BASIC_MINERAL_TYPE_IDS)
    if kind == "pi":
        return _types_for_ids(NAVY_HULL_PI_TYPE_IDS)
    raise ValueError(f"Unknown material kind: {kind!r}")


def order_mineral_and_pi_options(
    order: Optional[IndustryOrder] = None,
) -> Tuple[List[EveType], List[EveType]]:
    """Basic mineral and navy-hull PI checkbox options (no BOM)."""
    del order
    return (
        order_material_options(kind="mineral"),
        order_material_options(kind="pi"),
    )


def validate_mineral_coordinator_eve_type_ids(
    order: Optional[IndustryOrder],
    eve_type_ids: Sequence[int],
) -> Optional[str]:
    """Return error detail if any type is not a basic mineral."""
    del order
    if not eve_type_ids:
        return "Select at least one mineral."
    allowed = basic_mineral_type_ids()
    requested = {int(t) for t in eve_type_ids}
    invalid = requested - allowed
    if invalid:
        return "These types are not basic minerals: " + ", ".join(
            str(t) for t in sorted(invalid)
        )
    return None


def validate_pi_coordinator_eve_type_ids(
    order: Optional[IndustryOrder],
    eve_type_ids: Sequence[int],
) -> Optional[str]:
    """Return error detail if any type is not navy-hull PI."""
    del order
    if not eve_type_ids:
        return "Select at least one PI material."
    allowed = navy_hull_pi_type_ids()
    requested = {int(t) for t in eve_type_ids}
    invalid = requested - allowed
    if invalid:
        return "These types are not navy-hull PI materials: " + ", ".join(
            str(t) for t in sorted(invalid)
        )
    return None
