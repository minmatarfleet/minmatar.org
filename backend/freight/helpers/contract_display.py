"""Shared freight contract display helpers (API responses and CSV export)."""

from __future__ import annotations

from eveonline.helpers.characters import character_primary
from eveonline.models import EveCharacter, EveCorporation, EveLocation
from eveuniverse.models import EveStation
from freight.models import FREIGHT_CORPORATION_ID
from structures.models import EveStructure

FREIGHT_CORP_FALLBACK_NAME = "Freight corp"


def resolve_location_names(location_ids):
    """Bulk-resolve location IDs to freight short names when available."""
    if not location_ids:
        return {}

    names = {}
    for location in EveLocation.objects.filter(location_id__in=location_ids):
        if location.short_name:
            names[location.location_id] = location.short_name

    unresolved = location_ids - set(names)
    if not unresolved:
        return names

    station_ids = {lid for lid in unresolved if 60_000_000 < lid < 61_000_000}
    structure_ids = unresolved - station_ids

    if station_ids:
        for station in EveStation.objects.filter(
            id__in=station_ids
        ).select_related("eve_solar_system"):
            if station.eve_solar_system:
                names[station.id] = station.eve_solar_system.name
            else:
                names[station.id] = station.name

    if structure_ids:
        for structure in EveStructure.objects.filter(id__in=structure_ids):
            # Prefer system-style short labels when EveLocation is missing.
            names[structure.id] = (
                structure.name.split(" - ", 1)[0]
                if " - " in structure.name
                else structure.name
            )

    for lid in unresolved:
        if lid not in names:
            names[lid] = "Unknown" if lid in station_ids else "Structure"

    return names


def resolve_characters(character_ids):
    """Bulk-fetch EveCharacters, pre-loading the user → primary-character chain."""
    if not character_ids:
        return {}
    chars = EveCharacter.objects.filter(
        character_id__in=character_ids
    ).select_related(
        "user__eveplayer__primary_character",
        "token__user__eveplayer__primary_character",
    )
    return {c.character_id: c for c in chars}


def display_character(char):
    """Resolve an EveCharacter to its User's primary character, falling back to itself."""
    if not char:
        return None
    try:
        primary = character_primary(char)
        return primary if primary else char
    except Exception:
        return char


def completed_by_display(char, chars_by_user_id=None):
    """Resolve acceptor EveCharacter → User → primary character for display.

    Falls back to the acceptor character when it has no linked user, so
    in-progress contracts still show who is servicing them.

    Optional chars_by_user_id avoids N+1 when bulk-exporting (user_id → chars).
    """
    if not char:
        return None
    user = char.user or (
        char.token.user if getattr(char, "token", None) else None
    )
    if not user:
        return char
    try:
        primary = user.eveplayer.primary_character
        if primary:
            return primary
    except Exception:
        pass
    if chars_by_user_id is not None:
        chars = chars_by_user_id.get(user.id, [])
    else:
        chars = list(user.evecharacter_set.all())
    return min(chars, key=lambda c: (c.character_name or ""), default=char)


def freight_corp_display_name():
    corp = (
        EveCorporation.objects.filter(corporation_id=FREIGHT_CORPORATION_ID)
        .only("name")
        .first()
    )
    if corp and corp.name:
        return corp.name
    return FREIGHT_CORP_FALLBACK_NAME
