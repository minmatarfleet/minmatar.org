"""Helpers to update a character's mining ledger from ESI."""

import logging
from datetime import date, timedelta

from django.utils import timezone

from eveuniverse.models import EveType, EveTypeMaterial

from eveonline.client import EsiClient
from eveonline.models import EveCharacter
from eveonline.models.characters import (
    EveCharacterMiningDelta,
    EveCharacterMiningEntry,
)

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


def _record_delta(
    character, eve_type, solar_system_id, entry_date, quantity, previous
) -> None:
    """Store what this sync added. Only today's and yesterday's rows count, so
    a pilot's first sync doesn't replay their whole 30-day ledger as new."""
    added = quantity - (previous or 0)
    if added <= 0:
        return
    if entry_date < timezone.now().date() - timedelta(days=1):
        return
    EveCharacterMiningDelta.objects.create(
        character=character,
        eve_type=eve_type,
        solar_system_id=solar_system_id,
        quantity=added,
        observed_at=timezone.now(),
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
    synced = sync_character_mining(character)
    return synced or 0


def sync_character_mining(character: EveCharacter) -> int | None:
    """
    Fetch the ledger from ESI and upsert it.

    Returns the number of entries synced, or None when nothing could be
    read (ESI-suspended character or an ESI error), so a caller that needs
    a fresh reading can tell "no mining" from "no answer".
    """
    if character.esi_suspended:
        logger.debug(
            "Skipping mining for ESI-suspended character %s",
            character.character_id,
        )
        return None

    esi = EsiClient(character)
    response = esi.get_character_mining_ledger()
    if not response.success():
        logger.warning(
            "Skipping mining for character %s, %s",
            character.character_id,
            response.response_code,
        )
        return None

    return _store_ledger_entries(character, response.results() or [])


def mining_totals_since(
    character: EveCharacter, since_date: date
) -> dict[str, int]:
    """Units mined per ore type ({str(type_id): qty}) on or after a day."""
    totals: dict[str, int] = {}
    rows = EveCharacterMiningEntry.objects.filter(
        character=character, date__gte=since_date
    ).values_list("eve_type_id", "quantity")
    for type_id, quantity in rows:
        key = str(type_id)
        totals[key] = totals.get(key, 0) + int(quantity)
    return totals


def _store_ledger_entries(character: EveCharacter, entries) -> int:
    eve_character_id = character.character_id
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

        previous = (
            EveCharacterMiningEntry.objects.filter(
                character=character,
                eve_type=eve_type,
                date=entry_date,
                solar_system_id=solar_system_id,
            )
            .values_list("quantity", flat=True)
            .first()
        )
        EveCharacterMiningEntry.objects.update_or_create(
            character=character,
            eve_type=eve_type,
            date=entry_date,
            solar_system_id=solar_system_id,
            defaults={"quantity": quantity},
        )
        _record_delta(
            character,
            eve_type,
            solar_system_id,
            entry_date,
            quantity,
            previous,
        )

    logger.info(
        "Synced %s mining entry(ies) for character %s",
        len(entries),
        eve_character_id,
    )
    return len(entries)
