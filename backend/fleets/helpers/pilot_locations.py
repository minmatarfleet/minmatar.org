"""
Where a user's characters are right now, for the fleet form-up card.

Read from ESI with the Desktop group's location scope and cached for a
minute per character. A character without the scope (or without a usable
token) comes back without a location; an ESI failure for one character
leaves that character's location empty and is not cached.
"""

from eveonline.client import (
    CHAR_ESI_SUSPENDED,
    NO_VALID_ACCESS_TOKEN,
    NO_VALID_ESI_TOKEN,
    EsiClient,
)
from eveonline.helpers.corporations.safe_cache import cache_get, cache_set
from eveuniverse.models import EveSolarSystem

LOCATION_TTL_SECONDS = 60
NO_SCOPE_CODES = (
    NO_VALID_ESI_TOKEN,
    NO_VALID_ACCESS_TOKEN,
    CHAR_ESI_SUSPENDED,
)


def _cache_key(character_id: int) -> str:
    return f"fleets:pilot-location:v1:{character_id}"


def character_location(character) -> dict:
    """{has_location_scope, solar_system_id, station_id, structure_id}."""
    key = _cache_key(character.character_id)
    cached = cache_get(key)
    if cached is not None:
        return cached

    response = EsiClient(character).get_character_location()
    if response.response_code in NO_SCOPE_CODES:
        location = {"has_location_scope": False}
    elif response.success() and isinstance(response.data, dict):
        location = {
            "has_location_scope": True,
            "solar_system_id": response.data.get("solar_system_id"),
            "station_id": response.data.get("station_id"),
            "structure_id": response.data.get("structure_id"),
        }
    else:
        return {"has_location_scope": True}
    cache_set(key, location, LOCATION_TTL_SECONDS)
    return location


def pilot_locations(characters) -> list[dict]:
    """One row per character, with solar system names from the SDE cache."""
    rows = []
    for character in characters:
        location = character_location(character)
        rows.append(
            {
                "character_id": character.character_id,
                "character_name": character.character_name,
                "solar_system_id": location.get("solar_system_id"),
                "station_id": location.get("station_id"),
                "structure_id": location.get("structure_id"),
                "has_location_scope": location["has_location_scope"],
            }
        )
    names = dict(
        EveSolarSystem.objects.filter(
            id__in={r["solar_system_id"] for r in rows if r["solar_system_id"]}
        ).values_list("id", "name")
    )
    for row in rows:
        row["solar_system_name"] = names.get(row["solar_system_id"])
    return rows
