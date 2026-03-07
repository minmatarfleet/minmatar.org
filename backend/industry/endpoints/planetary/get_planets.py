"""GET "" - planet summary: list characters on a planet (query by planet_id or solar_system_id)."""

from typing import List, Optional

from ninja import Query

from eveonline.models import EveCharacterPlanet
from eveonline.helpers.characters import character_primary

from industry.endpoints.planetary.schemas import (
    CharacterRef,
    PlanetSummaryItem,
)
from industry.helpers.alliance import get_alliance_character_ids

PATH = ""
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Planet summary: list primary + actual character for colonies on a planet or in a system",
    "response": {200: List[PlanetSummaryItem]},
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
    result = []
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
        result.append(
            PlanetSummaryItem(
                primary_character=primary_ref,
                actual_character=actual,
            )
        )
    return result
