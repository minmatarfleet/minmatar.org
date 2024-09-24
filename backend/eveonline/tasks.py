import json
import logging

from esi.clients import EsiClientProvider
from esi.models import Token
from eveuniverse.models import EveFaction

from app.celery import app

from .helpers.assets import create_character_assets
from .helpers.skills import (
    create_eve_character_skillset,
    upsert_character_skills,
)
from .models import (
    EveAlliance,
    EveCharacter,
    EveCharacterKillmail,
    EveCharacterKillmailAttacker,
    EveCorporation,
    EveSkillset,
)

esi = EsiClientProvider()
logger = logging.getLogger(__name__)


@app.task
def update_character_affilliations():
    known_corporation_ids = set()
    known_alliance_ids = set()
    known_faction_ids = set()
    character_ids = EveCharacter.objects.values_list("character_id", flat=True)

    character_id_batches = []
    # batch in groups of 1000
    for i in range(0, len(character_ids), 1000):
        character_id_batches.append(character_ids[i : i + 1000])

    for character_ids_batch in character_id_batches:
        logger.info(
            "Processing batch of %s characters", len(character_ids_batch)
        )
        results = esi.client.Character.post_characters_affiliation(
            characters=character_ids_batch
        ).results()
        for result in results:
            character_id = result["character_id"]
            corporation_id = result.get("corporation_id")
            alliance_id = result.get("alliance_id")
            faction_id = result.get("faction_id")

            character = EveCharacter.objects.get(character_id=character_id)
            if (
                corporation_id
                and corporation_id not in known_corporation_ids
                and not EveCorporation.objects.filter(
                    corporation_id=corporation_id
                ).exists()
            ):
                logger.info(
                    "Creating corporation %s for character %s",
                    corporation_id,
                    character_id,
                )
                EveCorporation.objects.create(corporation_id=corporation_id)
                known_corporation_ids.add(corporation_id)
            if (
                alliance_id
                and alliance_id not in known_alliance_ids
                and not EveAlliance.objects.filter(
                    alliance_id=alliance_id
                ).exists()
            ):
                logger.info(
                    "Creating alliance %s for character %s",
                    alliance_id,
                    character_id,
                )
                EveAlliance.objects.create(alliance_id=alliance_id)
                known_alliance_ids.add(alliance_id)

            if (
                faction_id
                and faction_id not in known_faction_ids
                and not EveFaction.objects.filter(id=faction_id).exists()
            ):
                logger.info(
                    "Creating faction %s for character %s",
                    faction_id,
                    character_id,
                )
                EveFaction.objects.get_or_create_esi(id=faction_id)
                known_faction_ids.add(faction_id)

            updated = False
            if (corporation_id and not character.corporation) or (
                corporation_id
                and corporation_id != character.corporation.corporation_id
            ):
                character.corporation = EveCorporation.objects.get(
                    corporation_id=corporation_id
                )
                updated = True

            if (alliance_id and not character.alliance) or (
                alliance_id and alliance_id != character.alliance.alliance_id
            ):
                character.alliance = EveAlliance.objects.get(
                    alliance_id=alliance_id
                )
                updated = True

            if not alliance_id and character.alliance:
                character.alliance = None
                updated = True

            if (
                (faction_id and not character.faction)
                or faction_id
                and (faction_id != character.faction.id)
            ):
                character.faction = EveFaction.objects.get(id=faction_id)
                updated = True

            if not faction_id and character.faction:
                character.faction = None
                updated = True

            if updated:
                logger.info(
                    "Updating affiliations for character %s", character_id
                )
                character.save()


@app.task
def update_characters():
    for character in EveCharacter.objects.all():
        logger.info("Updating character %s", character.character_id)
        update_character_skills.apply_async(
            args=[character.character_id], countdown=character.id % 86400
        )
        update_character_assets.apply_async(
            args=[character.character_id], countdown=character.id % 86400
        )


@app.task
def update_character_skills(eve_character_id):
    logger.info("Updating skills for character %s", eve_character_id)
    upsert_character_skills(eve_character_id)
    # update skillsets
    for skillset in EveSkillset.objects.all():
        create_eve_character_skillset(eve_character_id, skillset)


@app.task
def update_character_assets(eve_character_id):
    logger.info("Updating assets for character %s", eve_character_id)
    required_scopes = [
        "esi-assets.read_assets.v1",
        "esi-universe.read_structures.v1",
    ]
    token = Token.objects.filter(
        character_id=eve_character_id, scopes__name__in=required_scopes
    ).first()
    if token is None:
        logger.info("Skipping asset update for character %s", eve_character_id)
        return
    esi_assets = esi.client.Assets.get_characters_character_id_assets(
        character_id=eve_character_id, token=token.valid_access_token()
    ).results()
    character = EveCharacter.objects.get(character_id=eve_character_id)
    character.assets_json = json.dumps(esi_assets)
    character.save()
    create_character_assets(character)


@app.task(rate_limit="10/m")
def update_character_killmails(eve_character_id):
    logger.info("Updating killmails for character %s", eve_character_id)
    required_scopes = [
        "esi-killmails.read_killmails.v1",
    ]
    token = Token.objects.filter(
        character_id=eve_character_id, scopes__name__in=required_scopes
    ).first()
    if token is None:
        logger.info(
            "Skipping killmail update for character %s", eve_character_id
        )
        return
    esi_killmails = (
        esi.client.Killmails.get_characters_character_id_killmails_recent(
            character_id=eve_character_id, token=token.valid_access_token()
        ).results()
    )
    character = EveCharacter.objects.get(character_id=eve_character_id)
    for killmail in esi_killmails:
        details = esi.client.Killmails.get_killmails_killmail_id_killmail_hash(
            killmail_id=killmail["killmail_id"],
            killmail_hash=killmail["killmail_hash"],
        ).results()
        killmail_id = killmail["killmail_id"]
        if not EveCharacterKillmail.objects.filter(id=killmail_id).exists():
            killmail = EveCharacterKillmail.objects.create(
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
                    killmail=killmail,
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


@app.task
def update_corporations():
    for corporation in EveCorporation.objects.all():
        update_corporation.apply_async(args=[corporation.corporation_id])


@app.task
def update_corporation(corporation_id):
    logger.info("Updating corporation %s", corporation_id)
    corporation = EveCorporation.objects.get(corporation_id=corporation_id)
    corporation.populate()
    if not corporation:
        return
    # fetch and set members if active
    if corporation.active and (corporation.type in ["alliance", "associate"]):
        required_scopes = ["esi-corporations.read_corporation_membership.v1"]
        token = Token.objects.filter(
            character_id=corporation.ceo.character_id,
            scopes__name__in=required_scopes,
        ).first()
        logger.info("Updating corporation members for %s", corporation.name)
        esi_members = (
            esi.client.Corporation.get_corporations_corporation_id_members(
                corporation_id=corporation_id,
                token=token.valid_access_token(),
            ).results()
        )
        for member_id in esi_members:
            if not EveCharacter.objects.filter(
                character_id=member_id
            ).exists():
                logger.info(
                    "Creating character %s for corporation %s",
                    member_id,
                    corporation.name,
                )
                EveCharacter.objects.create(character_id=member_id)
