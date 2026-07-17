"""Sync character jump clones and medical clone from ESI."""

import logging

from django.utils import timezone

from eveonline.client import EsiClient
from eveonline.helpers.implants import (
    build_clone_implant_list,
    total_implant_value_isk,
)
from eveonline.helpers.locations import resolve_location_name
from eveonline.models import EveCharacter, EveCharacterClone

logger = logging.getLogger(__name__)

CLONE_SCOPES = [
    "esi-clones.read_clones.v1",
    "esi-clones.read_implants.v1",
]


def update_character_clones(eve_character_id: int) -> int:
    """
    Fetch clones and active implants from ESI and refresh stored clone rows.
    Returns the number of jump clones synced.
    """
    character = EveCharacter.objects.filter(
        character_id=eve_character_id
    ).first()
    if not character:
        logger.warning(
            "Character %s not found, skipping clone sync",
            eve_character_id,
        )
        return 0
    if character.esi_suspended:
        logger.debug(
            "Skipping clones for ESI-suspended character %s",
            eve_character_id,
        )
        return 0

    esi = EsiClient(character)
    clones_response = esi.get_character_clones()
    if not clones_response.success():
        logger.warning(
            "Skipping clones for character %s, %s",
            eve_character_id,
            clones_response.response_code,
        )
        return 0

    implants_response = esi.get_character_implants()
    if not implants_response.success():
        logger.warning(
            "Skipping implants for character %s, %s",
            eve_character_id,
            implants_response.response_code,
        )
        return 0

    clones_data = clones_response.results() or {}
    active_implant_ids = sorted(
        {int(tid) for tid in (implants_response.results() or [])}
    )

    home = clones_data.get("home_location") or {}
    home_location_id = home.get("location_id")
    home_location_type = home.get("location_type")
    character.medical_clone_location_id = home_location_id
    character.medical_clone_location_name = resolve_location_name(
        home_location_id, home_location_type
    )
    # Persist currently worn implants even when the body is not a jump clone
    # (home/medical), so reprocessing RX bonuses still resolve.
    character.active_implants = active_implant_ids
    character.clones_synced_at = timezone.now()
    character.save(
        update_fields=[
            "medical_clone_location_id",
            "medical_clone_location_name",
            "active_implants",
            "clones_synced_at",
        ]
    )

    jump_clones = clones_data.get("jump_clones") or []
    EveCharacterClone.objects.filter(character=character).delete()

    created = 0
    for jump_clone in jump_clones:
        implant_type_ids = jump_clone.get("implants") or []
        implants = build_clone_implant_list(implant_type_ids)
        location_id = jump_clone.get("location_id")
        location_type = jump_clone.get("location_type")
        EveCharacterClone.objects.create(
            character=character,
            clone_id=jump_clone["jump_clone_id"],
            name=jump_clone.get("name") or "",
            location_id=location_id,
            location_name=resolve_location_name(location_id, location_type),
            implants=implants,
            total_value_isk=total_implant_value_isk(implants),
            is_active=False,
        )
        created += 1

    match_active_implants_to_clone(character, active_implant_ids)
    logger.info(
        "Synced %s jump clone(s) for character %s",
        created,
        eve_character_id,
    )
    return created


def match_active_implants_to_clone(
    character: EveCharacter, active_implant_type_ids: list[int]
) -> None:
    """Mark the jump clone whose implant set matches active implants."""
    active_set = {int(tid) for tid in active_implant_type_ids}
    clones = list(EveCharacterClone.objects.filter(character=character))
    for clone in clones:
        clone_set = {
            int(item["type_id"])
            for item in (clone.implants or [])
            if item.get("type_id") is not None
        }
        clone.is_active = clone_set == active_set
        clone.save(update_fields=["is_active"])
