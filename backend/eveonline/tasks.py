import json
import logging

from esi.clients import EsiClientProvider
from esi.models import Token

from app.celery import app
from eveonline.helpers.affiliations import (
    create_or_update_affiliation_entities,
    update_character_with_affiliations,
)
from groups.tasks import update_affiliation

from .client import EsiClient
from .helpers.assets import create_character_assets
from .helpers.skills import (
    create_eve_character_skillset,
    upsert_character_skills,
)
from .routers.characters import scope_group
from .models import (
    EvePlayer,
    EveCharacter,
    EveCharacterKillmail,
    EveCharacterKillmailAttacker,
    EveCorporation,
    EveAlliance,
    EveSkillset,
)

esi = EsiClientProvider()
logger = logging.getLogger(__name__)


@app.task
def update_character_affilliations():
    character_ids = EveCharacter.objects.exclude(token=None).values_list(
        "character_id", flat=True
    )
    logger.info(
        "Update character affiliations, %d characters found",
        len(character_ids),
    )

    character_id_batches = []
    # batch in groups of 1000
    for i in range(0, len(character_ids), 1000):
        character_id_batches.append(character_ids[i : i + 1000])

    for character_ids_batch in character_id_batches:
        results = esi.client.Character.post_characters_affiliation(
            characters=character_ids_batch
        ).results()
        logger.info(
            "Update character affiliations, processing %d characters, %d results",
            len(character_ids_batch),
            len(results),
        )
        update_count = 0
        for result in results:
            character_id = result["character_id"]
            corporation_id = result.get("corporation_id")
            alliance_id = result.get("alliance_id")
            faction_id = result.get("faction_id")

            character = EveCharacter.objects.get(character_id=character_id)

            create_or_update_affiliation_entities(
                corporation_id=corporation_id,
                alliance_id=alliance_id,
                faction_id=faction_id,
            )
            updated = update_character_with_affiliations(
                character_id=character_id,
                corporation_id=corporation_id,
                alliance_id=alliance_id,
                faction_id=faction_id,
            )

            if updated:
                logger.info(
                    "Update character affiliations, character updated: %s",
                    character_id,
                )
                update_count += 1
                update_affiliation.apply_async(args=[character.token.user.id])

        logger.info(
            "Update character affiliations complete with %d changes",
            update_count,
        )


@app.task
def update_alliance_character_assets():
    counter = 0
    for character in EveCharacter.objects.filter(
        alliance__name="Minmatar Fleet Alliance"
    ).exclude(token=None):
        logger.info("Updating assets for character %s", character.character_id)
        update_character_assets.apply_async(
            args=[character.character_id], countdown=counter % 3600
        )
        counter += 1


@app.task
def update_alliance_character_skills():
    counter = 0
    for character in EveCharacter.objects.filter(
        alliance__name="Minmatar Fleet Alliance"
    ).exclude(token=None):
        logger.info("Updating skills for character %s", character.character_id)
        update_character_skills.apply_async(
            args=[character.character_id], countdown=counter % 3600
        )
        counter += 1


@app.task
def update_alliance_character_killmails():
    counter = 0
    for character in EveCharacter.objects.filter(
        alliance__name="Minmatar Fleet Alliance"
    ).exclude(token=None):
        logger.info(
            "Updating killmails for character %s", character.character_id
        )
        update_character_killmails.apply_async(
            args=[character.character_id], countdown=counter % 3600
        )
        counter += 1


@app.task
def update_character_skills(eve_character_id):
    character = EveCharacter.objects.get(character_id=eve_character_id)
    if character.esi_suspended:
        logger.info(
            "Skipping skills update for character %s", eve_character_id
        )
        return

    logger.info("Updating skills for character %s", eve_character_id)
    upsert_character_skills(eve_character_id)
    # update skillsets
    for skillset in EveSkillset.objects.all():
        create_eve_character_skillset(eve_character_id, skillset)


@app.task
def update_character_assets(eve_character_id):
    character = EveCharacter.objects.get(character_id=eve_character_id)

    logger.info("Updating assets for character %s", eve_character_id)

    response = EsiClient(character).get_character_assets()
    if not response.success():
        logger.error(
            "Error %d fetching assets for %s (%d)",
            response.response_code,
            character.character_name,
            character.character_id,
        )
        return

    character.assets_json = json.dumps(response.results())
    character.save()
    create_character_assets(character)


@app.task(rate_limit="10/m")
def update_character_killmails(eve_character_id):
    character = EveCharacter.objects.get(character_id=eve_character_id)

    logger.info("Updating killmails for character %s", eve_character_id)
    required_scopes = [
        "esi-killmails.read_killmails.v1",
    ]
    token = Token.get_token(character.character_id, required_scopes)
    if character.esi_suspended or not token:
        logger.info(
            "Skipping killmail update for character %s", eve_character_id
        )
        return
    esi_killmails = (
        esi.client.Killmails.get_characters_character_id_killmails_recent(
            character_id=eve_character_id, token=token.valid_access_token()
        ).results()
    )

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
        # required_scopes = ["esi-corporations.read_corporation_membership.v1"]
        # token = Token.get_token(corporation.ceo.character_id, required_scopes)
        # if not token:
        #     logger.warning("No valid CEO token for %s", corporation.name)
        #     return

        # logger.info("Updating corporation members for %s", corporation.name)
        # esi_members = (
        #     esi.client.Corporation.get_corporations_corporation_id_members(
        #         corporation_id=corporation_id,
        #         token=token.valid_access_token(),
        #     ).results()
        # )
        esi_members = EsiClient(corporation.ceo).get_corporation_members(
            corporation.corporation_id
        )
        for member_id in esi_members.results():
            if not EveCharacter.objects.filter(
                character_id=member_id
            ).exists():
                logger.info(
                    "Creating character %s for corporation %s",
                    member_id,
                    corporation.name,
                )
                EveCharacter.objects.create(character_id=member_id)


@app.task
def fixup_character_tokens():
    """Fix incorrectly linked or identified ESI tokens."""
    for character in EveCharacter.objects.all():
        updated = False

        tokens = Token.objects.filter(character_id=character.character_id)

        if tokens.count() == 1 and not character.token:
            # Character has a single tokem but it isn't linked
            # so link it
            character.token = tokens.first()
            updated = True

        if character.token and not character.esi_token_level:
            character.esi_token_level = scope_group(character.token)
            updated = True

        if updated:
            character.save()


@app.task
def deduplicate_alliances():
    """Remove duplicate alliance instances"""

    previous_id = -1
    for alliance in EveAlliance.objects.all().order_by("alliance_id"):
        if alliance.alliance_id == previous_id:
            logger.warning(
                "Removing duplicate alliance, %d %s",
                alliance.alliance_id,
                alliance.name,
            )
            alliance.delete()
        previous_id = alliance.alliance_id


@app.task
def setup_players():
    """Setup EvePlayer entities based on primary character data"""

    created = 0
    for char in EveCharacter.objects.filter(is_primary=True):
        if not char.user:
            logger.warning(
                "EveCharacter with primary but not user: %s",
                char.character_name,
            )
            continue
        _, created = EvePlayer.objects.get_or_create(
            user=char.user,
            defaults={
                "primary_character": char,
                "nickname": char.user.username,
            },
        )
        if created:
            logger.info("Created EvePlayer %s", char.user.username)
            created += 1

    logger.info("EvePlayers created: %d", created)


@app.task
def delete_orphan_players():
    deleted = 0
    for player in EvePlayer.objects.filter(user__isnull=True):
        player.delete()
        logger.info(
            "Deleted orphan EvePlayer for %s",
            (
                player.primary_character.character_name
                if player.primary_character
                else "Unknown"
            ),
        )
        deleted += 1
    logger.info("EvePlayers deleted: %d", deleted)
