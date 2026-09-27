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


def _sde_connect() -> sqlite3.Connection | None:
    path = sde_sqlite_path()
    if path is None:
        return None
    try:
        return sqlite3.connect(str(path))
    except sqlite3.Error:
        logger.exception("Could not open SDE sqlite at %s", path)
        return None


@lru_cache(maxsize=64)
def _system_ids_for(
    scope: str, constellation_id: int | None, region_id: int | None
) -> frozenset[int]:
    connection = _sde_connect()
    if connection is None:
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


def resolve_solar_system(
    name: str = "", solar_system_id: int | None = None
) -> tuple[int | None, str, int | None]:
    """Resolve a system by name or id → (id, canonical name, region_id)."""
    name = (name or "").strip()
    if not solar_system_id and name.isdigit():
        solar_system_id = int(name)
        name = ""

    connection = _sde_connect()
    if connection is None:
        return solar_system_id, name, None
    try:
        if solar_system_id:
            row = connection.execute(
                "SELECT solarSystemID, solarSystemName, regionID "
                "FROM mapSolarSystems WHERE solarSystemID = ?",
                (solar_system_id,),
            ).fetchone()
        elif name:
            row = connection.execute(
                "SELECT solarSystemID, solarSystemName, regionID "
                "FROM mapSolarSystems WHERE solarSystemName = ? "
                "COLLATE NOCASE",
                (name,),
            ).fetchone()
        else:
            return None, "", None
        if not row:
            return solar_system_id, name, None
        return int(row[0]), str(row[1]), int(row[2]) if row[2] else None
    finally:
        connection.close()


def resolve_constellation(
    name: str = "", constellation_id: int | None = None
) -> tuple[int | None, str]:
    """Resolve a constellation by name or id → (id, canonical name)."""
    name = (name or "").strip()
    if not constellation_id and name.isdigit():
        constellation_id = int(name)
        name = ""

    connection = _sde_connect()
    if connection is None:
        return constellation_id, name
    try:
        if constellation_id:
            row = connection.execute(
                "SELECT constellationID, constellationName "
                "FROM mapConstellations WHERE constellationID = ?",
                (constellation_id,),
            ).fetchone()
        elif name:
            row = connection.execute(
                "SELECT constellationID, constellationName "
                "FROM mapConstellations WHERE constellationName = ? "
                "COLLATE NOCASE",
                (name,),
            ).fetchone()
        else:
            return None, ""
        if not row:
            return constellation_id, name
        return int(row[0]), str(row[1])
    finally:
        connection.close()


def resolve_region(
    name: str = "", region_id: int | None = None
) -> tuple[int | None, str]:
    """Resolve a region by name or id → (id, canonical name)."""
    name = (name or "").strip()
    if not region_id and name.isdigit():
        region_id = int(name)
        name = ""

    connection = _sde_connect()
    if connection is None:
        return region_id, name
    try:
        if region_id:
            row = connection.execute(
                "SELECT regionID, regionName FROM mapRegions "
                "WHERE regionID = ?",
                (region_id,),
            ).fetchone()
        elif name:
            row = connection.execute(
                "SELECT regionID, regionName FROM mapRegions "
                "WHERE regionName = ? COLLATE NOCASE",
                (name,),
            ).fetchone()
        else:
            return None, ""
        if not row:
            return region_id, name
        return int(row[0]), str(row[1])
    finally:
        connection.close()
