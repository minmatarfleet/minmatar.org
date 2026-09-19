"""Operational state from a warzone jump graph.

CCP marks every Faction Warfare system frontline, command operations or
rearguard depending on how close it sits to enemy-held space, and that state
multiplies complex LP by 1.5, 1.0 or 0.01. ESI does not expose it, so we
derive it from system adjacency.

The graph is a fixture exported once from the SDE by
``manage.py export_warzone_jump_graph``. Without the fixture every system
reports ``unknown``, which lowers the confidence of complex-class inference
rather than inventing a multiplier.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path

from django.conf import settings

from campaigns.models import OperationalState

logger = logging.getLogger(__name__)

FIXTURE_NAME = "warzone_jump_graph.json"
MINMATAR_FACTION_ID = 500002
AMARR_FACTION_ID = 500003


def fixture_path() -> Path:
    return Path(settings.BASE_DIR) / "campaigns" / "fixtures" / FIXTURE_NAME


@lru_cache(maxsize=1)
def load_graph() -> dict:
    """``{"edges": {system_id: [neighbour_ids]}, "owners": {...}}``."""
    path = fixture_path()
    if not path.exists():
        logger.info("No warzone jump graph fixture at %s", path)
        return {"edges": {}, "systems": {}}
    try:
        with path.open() as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        logger.exception("Could not read the warzone jump graph")
        return {"edges": {}, "systems": {}}
    return data


def neighbours(solar_system_id: int) -> list[int]:
    graph = load_graph()
    return graph.get("edges", {}).get(str(solar_system_id), [])


def classify_system(
    solar_system_id: int, owner_faction_id, owners: dict | None = None
) -> str:
    """Frontline when adjacent to an enemy-held FW system.

    Command operations when adjacent to one of our own frontlines, rearguard
    otherwise. ``owners`` is the whole warzone's ownership as ESI reported it;
    without it we cannot see past our own campaign systems and return unknown
    rather than guessing.
    """
    graph = load_graph()
    if not graph.get("edges"):
        return OperationalState.UNKNOWN
    if owner_faction_id is None or not owners:
        return OperationalState.UNKNOWN

    enemy = (
        AMARR_FACTION_ID
        if owner_faction_id == MINMATAR_FACTION_ID
        else MINMATAR_FACTION_ID
    )

    direct = neighbours(solar_system_id)
    if any(owners.get(neighbour) == enemy for neighbour in direct):
        return OperationalState.FRONTLINE

    for neighbour in direct:
        if owners.get(neighbour) != owner_faction_id:
            continue
        if any(
            owners.get(second) == enemy for second in neighbours(neighbour)
        ):
            return OperationalState.COMMAND

    return OperationalState.REARGUARD
