"""Helpers to update a character's mining ledger from ESI."""

import logging
from datetime import date

from eveuniverse.models import EveType, EveTypeMaterial

from eveonline.client import EsiClient
from eveonline.models import EveCharacter
from eveonline.models.characters import EveCharacterMiningEntry

logger = logging.getLogger(__name__)


def _ensure_type_materials(eve_type: EveType) -> None:
    """Load reprocessing materials from SDE if not already present."""
    if not EveTypeMaterial.objects.filter(eve_type=eve_type).exists():
        try:
            EveTypeMaterial.objects.update_or_create_api(eve_type=eve_type)
        except Exception:
            logger.debug(
                "Could not load type materials for %s (%s)",
                eve_type.name,
                eve_type.id,
                exc_info=True,
            )


def update_character_mining(eve_character_id: int) -> int:
    """
    Fetch the personal mining ledger from ESI and upsert
    EveCharacterMiningEntry rows.  Returns the number of entries synced.

    Also lazily loads EveTypeMaterial for each ore type so that the
    industry module can reverse-lookup ore -> mineral relationships.
    """
    character = EveCharacter.objects.filter(
        character_id=eve_character_id
    ).first()
    if not character:
        logger.warning(
            "Character %s not found, skipping mining sync",
            eve_character_id,
        )
        return 0
    if character.esi_suspended:
        logger.debug(
            "Skipping mining for ESI-suspended character %s",
            eve_character_id,
        )
        return 0

    esi = EsiClient(character)
    response = esi.get_character_mining_ledger()
    if not response.success():
        logger.warning(
            "Skipping mining for character %s, %s",
            eve_character_id,
            response.response_code,
        )
        return 0

    entries = response.results() or []
    seen_type_ids: set[int] = set()

    for entry in entries:
        type_id = entry["type_id"]
        entry_date = date.fromisoformat(entry["date"])
        quantity = entry["quantity"]
        solar_system_id = entry["solar_system_id"]

        eve_type, _ = EveType.objects.get_or_create_esi(id=type_id)

        if type_id not in seen_type_ids:
            seen_type_ids.add(type_id)
            _ensure_type_materials(eve_type)

        EveCharacterMiningEntry.objects.update_or_create(
            character=character,
            eve_type=eve_type,
            date=entry_date,
            solar_system_id=solar_system_id,
            defaults={"quantity": quantity},
        )

    logger.info(
        "Synced %s mining entry(ies) for character %s",
        len(entries),
        eve_character_id,
    )
    return len(entries)
