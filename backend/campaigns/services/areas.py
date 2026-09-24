"""Ops theater helpers: constellation/region → solar system ids.

Used for UI hints only (\"is this system in an ops area?\"). Kill ingest
never expands areas into systems.
"""

from __future__ import annotations

import logging
import sqlite3
from functools import lru_cache
from pathlib import Path

from django.conf import settings

from campaigns.models import AreaScope, CampaignArea

logger = logging.getLogger(__name__)


def sde_sqlite_path() -> Path | None:
    """Prefer an explicit setting, then the frontend SDE glob used by exports."""
    configured = getattr(settings, "EVE_SDE_SQLITE_PATH", None)
    if configured:
        path = Path(configured)
        return path if path.exists() else None
    base = Path(settings.BASE_DIR).parent / "frontend" / "app" / "src" / "data"
    if not base.exists():
        return None
    matches = sorted(base.glob("sde-*.sqlite"))
    return matches[-1] if matches else None


@lru_cache(maxsize=64)
def _system_ids_for(
    scope: str, constellation_id: int | None, region_id: int | None
) -> frozenset[int]:
    path = sde_sqlite_path()
    if path is None:
        return frozenset()
    try:
        connection = sqlite3.connect(str(path))
    except sqlite3.Error:
        logger.exception("Could not open SDE sqlite at %s", path)
        return frozenset()
    try:
        if scope == AreaScope.CONSTELLATION and constellation_id:
            rows = connection.execute(
                "SELECT solarSystemID FROM mapSolarSystems "
                "WHERE constellationID = ?",
                (constellation_id,),
            ).fetchall()
        elif scope == AreaScope.REGION and region_id:
            rows = connection.execute(
                "SELECT solarSystemID FROM mapSolarSystems WHERE regionID = ?",
                (region_id,),
            ).fetchall()
        else:
            return frozenset()
        return frozenset(int(row[0]) for row in rows)
    finally:
        connection.close()


def systems_in_area(area: CampaignArea) -> set[int]:
    """Solar system ids inside a constellation or region ops area."""
    return set(
        _system_ids_for(area.scope, area.constellation_id, area.region_id)
    )


def area_contains_system(area: CampaignArea, solar_system_id: int) -> bool:
    return solar_system_id in systems_in_area(area)
