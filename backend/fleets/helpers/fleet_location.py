"""Resolve EveLocation for fleet form-up."""

from __future__ import annotations

from eveonline.helpers.characters import (
    user_characters,
    user_primary_character,
)
from eveonline.models import EveLocation

from fleets.helpers.pilot_locations import character_location
from fleets.models import EveFleet


def match_fleets_active_location(text: str) -> EveLocation | None:
    needle = (text or "").strip().lower()
    if not needle:
        return None

    for location in EveLocation.objects.filter(fleets_active=True):
        if location.short_name.lower() == needle:
            return location
        if location.solar_system_name.lower() == needle:
            return location
        if location.location_name.lower().startswith(needle):
            return location
    return None


def resolve_scheduled_fleet_location(
    location_id: int | None,
) -> EveLocation | tuple[int, dict]:
    if location_id:
        location = EveLocation.objects.filter(
            location_id=location_id, fleets_active=True
        ).first()
        if location is None:
            return 400, {
                "detail": "Location does not exist or is not available for fleets"
            }
        return location

    location = EveLocation.objects.filter(staging_active=True).first()
    if location is None:
        return 400, {"detail": "No active staging location configured"}
    return location


def default_staging_location() -> EveLocation | None:
    return EveLocation.objects.filter(staging_active=True).first()


# At most this many of the user's characters are looked up in ESI to find
# where the fleet boss is docked (main first).
MAX_DOCKED_LOOKUPS = 5


def docked_form_up_location(user) -> EveLocation | None:
    """The fleet form-up location one of the user's characters is docked
    at, main first; None when none of them is docked at one."""
    locations = {
        location.location_id: location
        for location in EveLocation.objects.filter(fleets_active=True)
    }
    if not locations:
        return None
    primary = user_primary_character(user)
    characters = [primary] if primary else []
    characters += [
        character
        for character in user_characters(user).order_by("character_name")
        if not primary or character.character_id != primary.character_id
    ]
    for character in characters[:MAX_DOCKED_LOOKUPS]:
        where = character_location(character)
        place = where.get("structure_id") or where.get("station_id")
        if place in locations:
            return locations[place]
    return None


def default_form_up_location(user) -> EveLocation | None:
    """Where a flash form forms up by default: where the fleet boss is
    docked when that is a form-up location, else the staging."""
    return docked_form_up_location(user) or default_staging_location()


def backfill_missing_fleet_locations() -> int:
    """Assign staging to fleets with no form-up location. Returns rows updated."""
    staging = default_staging_location()
    if staging is None:
        return 0
    return EveFleet.objects.filter(location__isnull=True).update(
        location=staging
    )
