"""Helpers to update a character's ESI-derived data (assets, skills, killmails)."""

import logging
import time

from eveonline.client import EsiClient
from eveonline.models import (
    EveCharacter,
    EveCharacterKillmail,
    EveCharacterKillmailAttacker,
    EveSkillset,
)

from eveonline.helpers.characters.assets import create_character_assets
from eveonline.helpers.characters.skills import (
    create_eve_character_skillset,
    upsert_character_skills,
)

logger = logging.getLogger(__name__)


def update_character_assets(eve_character_id: int) -> tuple[int, int, int]:
    """Fetch assets from ESI and replace character's assets. Returns (created, updated, deleted)."""
    start = time.perf_counter()
    character = EveCharacter.objects.get(character_id=eve_character_id)
    logger.debug("Updating assets for character %s", eve_character_id)

    response = EsiClient(character).get_character_assets()
    if not response.success():
        logger.error(
            "Error %s fetching assets for %s",
            response.error_text(),
            character.summary(),
        )
        return 0, 0, 0

    fetch_time = time.perf_counter() - start
    created, updated, deleted = create_character_assets(
        character, response.results()
    )
    elapsed = time.perf_counter() - start
    logger.info(
        "Updated assets for %s in %.6f (%.6f) seconds (%d, %d, %d)",
        character.character_name,
        elapsed,
        fetch_time,
        created,
        updated,
        deleted,
    )
    return created, updated, deleted


def update_character_skills(eve_character_id: int) -> None:
    """Update skills and skillsets for a character."""
    character = EveCharacter.objects.get(character_id=eve_character_id)
    if character.esi_suspended:
        logger.info(
            "Skipping skills update for character %s", eve_character_id
        )
        return

    logger.info("Updating skills for character %s", eve_character_id)
    upsert_character_skills(eve_character_id)
    for skillset in EveSkillset.objects.all():
        create_eve_character_skillset(eve_character_id, skillset)


def update_character_killmails(eve_character_id: int) -> None:
    """Fetch recent killmails from ESI and create missing records."""
    character = EveCharacter.objects.get(character_id=eve_character_id)
    logger.info("Updating killmails for character %s", eve_character_id)
    esi = EsiClient(eve_character_id)

    response = esi.get_recent_killmails()
    if not response.success():
        logger.warning(
            "Skipping killmail update for character %s, %s",
            eve_character_id,
            response.response_code,
        )
        return

    for killmail in response.results():
        killmail_id = killmail["killmail_id"]
        response = esi.get_character_killmail(
            killmail_id, killmail["killmail_hash"]
        )
        details = response.results()
        if not EveCharacterKillmail.objects.filter(id=killmail_id).exists():
            killmail_obj = EveCharacterKillmail.objects.create(
                id=killmail_id,
                killmail_id=killmail_id,
                killmail_hash=killmail["killmail_hash"],
                solar_system_id=details["solar_system_id"],
                ship_type_id=details["victim"]["ship_type_id"],
                killmail_time=details["killmail_time"],
                victim_character_id=(
                    details["victim"]["character_id"]
                    if "character_id" in details["victim"]
                    else None
                ),
                victim_corporation_id=(
                    details["victim"]["corporation_id"]
                    if "corporation_id" in details["victim"]
                    else None
                ),
                victim_alliance_id=(
                    details["victim"]["alliance_id"]
                    if "alliance_id" in details["victim"]
                    else None
                ),
                victim_faction_id=(
                    details["victim"]["faction_id"]
                    if "faction_id" in details["victim"]
                    else None
                ),
                attackers=details["attackers"],
                items=details["victim"]["items"],
                character=character,
            )

            for attacker in details["attackers"]:
                EveCharacterKillmailAttacker.objects.create(
                    killmail=killmail_obj,
                    character_id=(
                        attacker["character_id"]
                        if "character_id" in attacker
                        else None
                    ),
                    corporation_id=(
                        attacker["corporation_id"]
                        if "corporation_id" in attacker
                        else None
                    ),
                    alliance_id=(
                        attacker["alliance_id"]
                        if "alliance_id" in attacker
                        else None
                    ),
                    faction_id=(
                        attacker["faction_id"]
                        if "faction_id" in attacker
                        else None
                    ),
                    ship_type_id=(
                        attacker["ship_type_id"]
                        if "ship_type_id" in attacker
                        else None
                    ),
                )
