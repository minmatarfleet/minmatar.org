"""Blueprint ME/TE defaults for the industry build planner."""

from __future__ import annotations

from typing import Tuple

from eveuniverse.models import EveType

# Eve dogma: metaGroupID. Faction (navy / pirate faction hulls) = 4.
DOGMA_META_GROUP_ID = 1692
META_GROUP_FACTION = 4.0

CATEGORY_SHIP = 6

# Fallback when dogma is missing (tests / partial SDE loads).
_NAVY_NAME_SUFFIXES = (
    "Navy Issue",
    "Fleet Issue",
)

# Default researched BPO assumptions (percent).
DEFAULT_BLUEPRINT_ME = 10.0
DEFAULT_BLUEPRINT_TE = 20.0


def is_faction_navy_hull(eve_type: EveType) -> bool:
    """
    True for Faction-meta ships (navy / pirate faction hulls).

    Prefers SDE dogma metaGroupID == Faction; falls back to navy naming
    suffixes used elsewhere in the codebase (Navy Issue / Fleet Issue).
    """
    group = getattr(eve_type, "eve_group", None)
    category_id = getattr(group, "eve_category_id", None) if group else None
    if category_id is None and group is not None:
        category = getattr(group, "eve_category", None)
        category_id = getattr(category, "id", None) if category else None
    if category_id != CATEGORY_SHIP:
        return False

    meta = (
        eve_type.dogma_attributes.filter(
            eve_dogma_attribute_id=DOGMA_META_GROUP_ID
        )
        .values_list("value", flat=True)
        .first()
    )
    if meta is not None and float(meta) == META_GROUP_FACTION:
        return True

    name = (eve_type.name or "").strip()
    return any(name.endswith(suffix) for suffix in _NAVY_NAME_SUFFIXES)


def default_blueprint_me_te_percent(eve_type: EveType) -> Tuple[float, float]:
    """Return default blueprint ME/TE as percents (10/20 or 0/0 for navy)."""
    if is_faction_navy_hull(eve_type):
        return 0.0, 0.0
    return DEFAULT_BLUEPRINT_ME, DEFAULT_BLUEPRINT_TE
