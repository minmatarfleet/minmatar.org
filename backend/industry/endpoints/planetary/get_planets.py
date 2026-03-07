"""GET "" - planet summary: all planets with colonies and characters on each (optional filter by planet_id or solar_system_id)."""

from typing import List, Optional

from ninja import Query

from eveonline.models import EveCharacterPlanet
from eveonline.helpers.characters import character_primary

from industry.endpoints.planetary.schemas import (
    CharacterRef,
    ColonyEntry,
    PlanetWithColoniesItem,
)
from industry.helpers.alliance import get_alliance_character_ids

PATH = ""
METHOD = "get"
ROUTE_SPEC = {
    "summary": "All planets with colonies: for each planet, list of characters (primary + actual) that have a colony",
    "response": {200: List[PlanetWithColoniesItem]},
}


def get_planets(
    request,
    planet_id: Optional[int] = Query(None),
    solar_system_id: Optional[int] = Query(None),
):
    alliance_cids = get_alliance_character_ids()
    qs = EveCharacterPlanet.objects.filter(
        character__character_id__in=alliance_cids,
    )
    if planet_id is not None:
        qs = qs.filter(planet_id=planet_id)
    if solar_system_id is not None:
        qs = qs.filter(solar_system_id=solar_system_id)
    qs = qs.select_related("character").order_by("planet_id", "character")

    # Group by planet: (planet_id, solar_system_id, planet_type) -> list of ColonyEntry
    planets_map = {}
    for plan in qs:
        char = plan.character
        actual_id = char.character_id
        actual_name = char.character_name or ""
        actual = CharacterRef(
            character_id=actual_id, character_name=actual_name
        )
        primary_id = actual_id
        primary_name = actual_name
        try:
            primary = character_primary(char)
        except (AttributeError, TypeError):
            primary = None
        if primary:
            primary_id = primary.character_id
            primary_name = primary.character_name or ""
        primary_ref = CharacterRef(
            character_id=primary_id, character_name=primary_name
        )
        key = (plan.planet_id, plan.solar_system_id, plan.planet_type or "")
        if key not in planets_map:
            planets_map[key] = []
        planets_map[key].append(
            ColonyEntry(
                primary_character=primary_ref,
                actual_character=actual,
            )
        )

    return [
        PlanetWithColoniesItem(
            planet_id=pid,
            solar_system_id=sid,
            planet_type=ptype,
            colonies=cols,
        )
        for (pid, sid, ptype), cols in sorted(planets_map.items())
    ]
