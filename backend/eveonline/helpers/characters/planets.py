"""Helpers to update a character's planetary interaction data from ESI."""

import logging
from datetime import datetime

import pytz
from django.utils import timezone
from eveuniverse.models import EveType

from eveonline.client import EsiClient
from eveonline.models import EveCharacter
from eveonline.models.characters import (
    EveCharacterPlanet,
    EveCharacterPlanetOutput,
)

logger = logging.getLogger(__name__)


def _parse_esi_date(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return (
            timezone.make_aware(value) if timezone.is_naive(value) else value
        )
    # pylint: disable=no-value-for-parameter
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = pytz.UTC.localize(dt)
    return dt


# PI pin group IDs for extractors (all planet-type variants share these groups)
_EXTRACTOR_GROUP_IDS = {1063}
# Factory groups: basic (1028) and advanced (1029) industry facilities, hi-tech (1030 is launchpad, skip)
_FACTORY_GROUP_IDS = {1028, 1029}


def _determine_factory_output(pin, routes):
    """
    Given a factory pin (has schematic_id), determine its output type_id
    by finding outbound routes from this pin.
    """
    pin_id = pin["pin_id"]
    for route in routes:
        if route["source_pin_id"] == pin_id:
            return route["content_type_id"]
    return None


def _extract_planet_outputs(planet_detail):
    """
    Analyse a planet's pins and routes to determine harvested and produced types.

    Returns two sets: (harvested_type_ids, produced_type_ids).
    """
    pins = planet_detail.get("pins", [])
    routes = planet_detail.get("routes", [])

    harvested = set()
    produced = set()

    for pin in pins:
        if pin.get("extractor_details"):
            product_type_id = pin["extractor_details"].get("product_type_id")
            if product_type_id:
                harvested.add(product_type_id)

        if pin.get("schematic_id"):
            output_type_id = _determine_factory_output(pin, routes)
            if output_type_id:
                produced.add(output_type_id)

    return harvested, produced


def update_character_planets(eve_character_id: int) -> int:
    """
    Fetch planetary colonies from ESI and update EveCharacterPlanet /
    EveCharacterPlanetOutput rows.  Returns the number of planets synced.
    """
    character = EveCharacter.objects.filter(
        character_id=eve_character_id
    ).first()
    if not character:
        logger.warning(
            "Character %s not found, skipping planets sync",
            eve_character_id,
        )
        return 0
    if character.esi_suspended:
        logger.debug(
            "Skipping planets for ESI-suspended character %s",
            eve_character_id,
        )
        return 0

    esi = EsiClient(character)
    planets_response = esi.get_character_planets()
    if not planets_response.success():
        logger.warning(
            "Skipping planets for character %s, %s",
            eve_character_id,
            planets_response.response_code,
        )
        return 0

    planets_data = planets_response.results() or []
    active_planet_ids = set()

    for planet_entry in planets_data:
        planet_id = planet_entry["planet_id"]
        active_planet_ids.add(planet_id)

        planet_obj, _ = EveCharacterPlanet.objects.update_or_create(
            character=character,
            planet_id=planet_id,
            defaults={
                "planet_type": planet_entry.get("planet_type", ""),
                "solar_system_id": planet_entry.get("solar_system_id", 0),
                "upgrade_level": planet_entry.get("upgrade_level", 0),
                "num_pins": planet_entry.get("num_pins", 0),
                "last_update": _parse_esi_date(
                    planet_entry.get("last_update")
                ),
            },
        )

        detail_response = esi.get_character_planet_details(planet_id)
        if not detail_response.success():
            logger.warning(
                "Could not fetch planet %s detail for character %s (%s)",
                planet_id,
                eve_character_id,
                detail_response.response_code,
            )
            continue

        harvested, produced = _extract_planet_outputs(
            detail_response.results()
        )

        _sync_planet_outputs(planet_obj, harvested, produced)

    # Remove planets the character no longer has colonies on
    EveCharacterPlanet.objects.filter(character=character).exclude(
        planet_id__in=active_planet_ids
    ).delete()

    logger.info(
        "Synced %s planet(s) for character %s",
        len(planets_data),
        eve_character_id,
    )
    return len(planets_data)


def _sync_planet_outputs(planet_obj, harvested_type_ids, produced_type_ids):
    """Replace the planet's output rows with the current set."""
    existing = {
        (o.eve_type_id, o.output_type): o.pk for o in planet_obj.outputs.all()
    }
    desired = set()
    for type_id in harvested_type_ids:
        desired.add((type_id, EveCharacterPlanetOutput.OutputType.HARVESTED))
    for type_id in produced_type_ids:
        desired.add((type_id, EveCharacterPlanetOutput.OutputType.PRODUCED))

    to_delete = set(existing.keys()) - desired
    to_create = desired - set(existing.keys())

    if to_delete:
        ids = [existing[key] for key in to_delete]
        EveCharacterPlanetOutput.objects.filter(pk__in=ids).delete()

    for type_id, output_type in to_create:
        eve_type, _ = EveType.objects.get_or_create_esi(id=type_id)
        EveCharacterPlanetOutput.objects.create(
            planet=planet_obj,
            eve_type=eve_type,
            output_type=output_type,
        )
