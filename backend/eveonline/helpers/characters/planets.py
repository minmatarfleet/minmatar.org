"""Helpers to update a character's planetary interaction data from ESI."""

import logging
from datetime import datetime
from decimal import Decimal

import pytz
from django.utils import timezone
from eveuniverse.models import EveType

from eveonline.client import EsiClient, esi_public
from eveonline.models import EveCharacter
from eveonline.models.characters import (
    EveCharacterPlanet,
    EveCharacterPlanetOutput,
)
from eveonline.models.planetary_schematic import EveUniverseSchematic

logger = logging.getLogger(__name__)

SECONDS_PER_DAY = 86400


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
    and quantity per cycle by finding outbound routes from this pin.
    Returns (content_type_id, quantity) or (None, None).
    """
    pin_id = pin["pin_id"]
    for route in routes:
        if route["source_pin_id"] == pin_id:
            return route["content_type_id"], route.get("quantity", 0)
    return None, None


def _extract_planet_outputs_with_daily(planet_detail, schematic_cycle_seconds):
    """
    Analyse a planet's pins and routes; return harvested and produced
    type_id -> daily_quantity (estimated units per day).

    schematic_cycle_seconds: dict schematic_id -> cycle_time in seconds
    (from EveUniverseSchematic). Used for factory daily output.
    """
    pins = planet_detail.get("pins", [])
    routes = planet_detail.get("routes", [])

    harvested = {}  # type_id -> daily_quantity
    produced = {}  # type_id -> daily_quantity

    for pin in pins:
        if pin.get("extractor_details"):
            ext = pin["extractor_details"]
            product_type_id = ext.get("product_type_id")
            if not product_type_id:
                continue
            cycle_time = ext.get("cycle_time") or 1
            qty_per_cycle = ext.get("qty_per_cycle") or 0
            daily = (
                Decimal(qty_per_cycle) / Decimal(cycle_time)
            ) * SECONDS_PER_DAY
            harvested[product_type_id] = (
                harvested.get(product_type_id, Decimal(0)) + daily
            )

        if pin.get("schematic_id"):
            output_type_id, quantity = _determine_factory_output(pin, routes)
            if not output_type_id:
                continue
            cycle_time = (
                schematic_cycle_seconds.get(pin["schematic_id"]) or 3600
            )
            qty = Decimal(quantity or 0)
            daily = (qty / Decimal(cycle_time)) * SECONDS_PER_DAY
            produced[output_type_id] = (
                produced.get(output_type_id, Decimal(0)) + daily
            )

    return harvested, produced


def _schematic_ids_from_planet_detail(planet_detail):
    """Return set of schematic_ids used by factory pins on this planet."""
    pins = planet_detail.get("pins", [])
    return {p["schematic_id"] for p in pins if p.get("schematic_id")}


def ensure_schematics_cached(schematic_ids):
    """
    Fetch PI schematics from ESI and store in EveUniverseSchematic.

    Public endpoint; safe to call with any list of schematic_ids (e.g. from
    planet pins). Missing or failed IDs are skipped; existing rows are updated.
    """
    if not schematic_ids:
        return
    esi = esi_public()
    for schematic_id in schematic_ids:
        try:
            response = esi.get_universe_schematic(schematic_id)
            if not response.success():
                logger.debug(
                    "Could not fetch schematic %s: %s",
                    schematic_id,
                    response.response_code,
                )
                continue
            data = response.results()
            EveUniverseSchematic.objects.update_or_create(
                schematic_id=schematic_id,
                defaults={
                    "schematic_name": data.get("schematic_name", ""),
                    "cycle_time": data.get("cycle_time", 0),
                },
            )
        except Exception as e:  # pylint: disable=broad-except
            logger.warning(
                "Failed to fetch/store schematic %s: %s",
                schematic_id,
                e,
            )


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
    seen_schematic_ids = set()

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

        detail_data = detail_response.results()
        planet_schematic_ids = _schematic_ids_from_planet_detail(detail_data)
        seen_schematic_ids |= planet_schematic_ids
        ensure_schematics_cached(planet_schematic_ids)

        cycle_map = dict(
            EveUniverseSchematic.objects.filter(
                schematic_id__in=planet_schematic_ids
            ).values_list("schematic_id", "cycle_time")
        )
        harvested, produced = _extract_planet_outputs_with_daily(
            detail_data, cycle_map
        )

        _sync_planet_outputs(planet_obj, harvested, produced)

    ensure_schematics_cached(seen_schematic_ids)

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


def _sync_planet_outputs(planet_obj, harvested_dict, produced_dict):
    """
    Replace the planet's output rows with the current set.
    harvested_dict and produced_dict are type_id -> daily_quantity.
    """
    desired = set()
    for type_id in harvested_dict:
        desired.add((type_id, EveCharacterPlanetOutput.OutputType.HARVESTED))
    for type_id in produced_dict:
        desired.add((type_id, EveCharacterPlanetOutput.OutputType.PRODUCED))

    existing = {
        (o.eve_type_id, o.output_type): o
        for o in planet_obj.outputs.select_related("eve_type").all()
    }
    to_delete = set(existing.keys()) - desired
    to_create = desired - set(existing.keys())

    if to_delete:
        ids = [existing[key].pk for key in to_delete]
        EveCharacterPlanetOutput.objects.filter(pk__in=ids).delete()

    for type_id, output_type in to_create:
        eve_type, _ = EveType.objects.get_or_create_esi(id=type_id)
        daily = (
            harvested_dict.get(type_id, Decimal(0))
            if output_type == EveCharacterPlanetOutput.OutputType.HARVESTED
            else produced_dict.get(type_id, Decimal(0))
        )
        EveCharacterPlanetOutput.objects.create(
            planet=planet_obj,
            eve_type=eve_type,
            output_type=output_type,
            daily_quantity=daily,
        )

    for (type_id, output_type), obj in existing.items():
        if (type_id, output_type) in desired:
            daily = (
                harvested_dict.get(type_id, Decimal(0))
                if output_type == EveCharacterPlanetOutput.OutputType.HARVESTED
                else produced_dict.get(type_id, Decimal(0))
            )
            if obj.daily_quantity != daily:
                obj.daily_quantity = daily
                obj.save(update_fields=["daily_quantity"])
