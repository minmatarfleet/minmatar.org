import logging
import time
from datetime import timedelta

from django.utils import timezone
from django.contrib.auth.models import User

from esi.models import Token

from app.celery import app
from eveonline.helpers.affiliations import update_character_with_affiliations
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
    EveCharacterAsset,
    EveCorporation,
    EveAlliance,
    EveSkillset,
)

logger = logging.getLogger(__name__)

task_config = {
    "async_apply_affiliations": True,
}


@app.task
def update_character_affilliations() -> int:
    character_ids = EveCharacter.objects.values_list("character_id", flat=True)
    logger.info(
        "Update character affiliations, %d characters found",
        len(character_ids),
    )

    character_id_batches = []
    # batch in groups of 1000
    for i in range(0, len(character_ids), 1000):
        character_id_batches.append(character_ids[i : i + 1000])

    update_count = 0

    for character_ids_batch in character_id_batches:
        results = (
            EsiClient(None)
            .get_character_affiliations(character_ids_batch)
            .results()
        )
        logger.info(
            "Update character affiliations, processing %d characters, %d results",
            len(character_ids_batch),
            len(results),
        )
        for result in results:
            character_id = result["character_id"]
            corporation_id = result.get("corporation_id")
            alliance_id = result.get("alliance_id")
            faction_id = result.get("faction_id")

            character = EveCharacter.objects.get(character_id=character_id)

            updated = update_character_with_affiliations(
                character_id=character_id,
                corporation_id=corporation_id,
                alliance_id=alliance_id,
                faction_id=faction_id,
            )

            if updated:
                logger.info(
                    "Update character affiliations, character updated: %s (%s)",
                    character_id,
                    character.user_id,
                )
                update_count += 1
                if character.user:
                    if task_config["async_apply_affiliations"]:
                        update_affiliation.apply_async(
                            args=[character.user.id]
                        )
                    else:
                        update_affiliation(character.user.id)

    logger.info(
        "Update character affiliations complete with %d changes",
        update_count,
    )
    return update_count


@app.task
def update_alliance_character_assets():
    # Get all characters in the alliance
    alliance_characters = EveCharacter.objects.filter(
        alliance__name="Minmatar Fleet Alliance"
    )

    # Get all users who have at least one character in the alliance
    users_with_alliance_chars = User.objects.filter(
        evecharacter__in=alliance_characters
    ).distinct()

    # Get all characters belonging to those users (including alts)
    all_characters = EveCharacter.objects.filter(
        user__in=users_with_alliance_chars
    ).exclude(token=None)

    counter = 0
    for character in all_characters:
        logger.debug(
            "Updating assets for character %s", character.character_id
        )
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
    fetch_str = f"{fetch_time:.6f}"

    created, updated, deleted = create_character_assets(
        character, response.results()
    )

    elapsed = time.perf_counter() - start
    elapsed_str = f"{elapsed:.6f}"

    logger.info(
        "Updated assets for %s in %s (%s) seconds (%d, %d, %d)",
        character.character_name,
        elapsed_str,
        fetch_str,
        created,
        updated,
        deleted,
    )

    return created, updated, deleted


def _delete_orphan_assets(delete: bool):
    """Delete asset records that aren't being updated"""

    cutoff = timezone.now() - timedelta(days=2)

    total = EveCharacterAsset.objects.count()
    to_delete = EveCharacterAsset.objects.filter(updated__lt=cutoff)

    logger.info(
        "Found %d of %d stale EveCharacterAsset rows",
        to_delete.count(),
        total,
    )

    if delete:
        deleted, _ = to_delete.delete()

        logger.info("Deleted %d EveCharacterAsset rows", deleted)


@app.task()
def find_orphan_assets():
    """Find asset records that aren't being updated"""
    _delete_orphan_assets(False)


@app.task()
def delete_orphan_assets():
    """Delete asset records that aren't being updated"""
    _delete_orphan_assets(True)


@app.task(rate_limit="10/m")
def update_character_killmails(eve_character_id):
    character = EveCharacter.objects.get(character_id=eve_character_id)

    logger.info("Updating killmails for character %s", eve_character_id)
    # required_scopes = [
    #     "esi-killmails.read_killmails.v1",
    # ]
    # token = Token.get_token(character.character_id, required_scopes)
    # if character.esi_suspended or not token:
    #     logger.info(
    #         "Skipping killmail update for character %s", eve_character_id
    #     )
    #     return
    # esi_killmails = (
    #     esi.client.Killmails.get_characters_character_id_killmails_recent(
    #         character_id=eve_character_id, token=token.valid_access_token()
    #     ).results()
    # )
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
        # details = esi.client.Killmails.get_killmails_killmail_id_killmail_hash(
        #     killmail_id=killmail["killmail_id"],
        #     killmail_hash=killmail["killmail_hash"],
        # ).results()
        killmail_id = killmail["killmail_id"]
        response = esi.get_character_killmail(
            killmail_id, killmail["killmail_hash"]
        )
        details = response.results()
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


ALLIED_ALLIANCE_NAMES = [
    "Minmatar Fleet Alliance",
    "Minmatar Fleet Associates",
]


@app.task
def update_corporations():
    for corporation in EveCorporation.objects.filter(
        alliance__name__in=ALLIED_ALLIANCE_NAMES
    ):
        update_corporation.apply_async(args=[corporation.corporation_id])


@app.task
def sync_alliance_corporations():
    """
    For each EveAlliance in the database, fetch corporation IDs from ESI
    (get_alliance_corporations) and get_or_create EveCorporation for each,
    then populate corporation details from ESI.
    """
    alliances = EveAlliance.objects.all().order_by("alliance_id")
    logger.info(
        "Syncing corporations for %d alliances",
        alliances.count(),
    )
    total_created = 0
    for alliance in alliances:
        esi_response = EsiClient(None).get_alliance_corporations(
            alliance.alliance_id
        )
        if not esi_response.success():
            logger.warning(
                "ESI error %d fetching corporations for alliance %s (%s)",
                esi_response.response_code,
                alliance.name or alliance.alliance_id,
                alliance.alliance_id,
            )
            continue
        corporation_ids = esi_response.results() or []
        logger.info(
            "Alliance %s (%s): %d corporations from ESI",
            alliance.name or alliance.alliance_id,
            alliance.alliance_id,
            len(corporation_ids),
        )
        for corporation_id in corporation_ids:
            corporation, created = EveCorporation.objects.get_or_create(
                corporation_id=corporation_id
            )
            if created:
                corporation.populate()
                total_created += 1
                logger.info(
                    "Created corporation %s (%s)",
                    corporation.name,
                    corporation_id,
                )
    logger.info(
        "sync_alliance_corporations complete: %d new corporations created",
        total_created,
    )
    return total_created


def _all_roles_for_member(role_data):
    """Collect all role names for a member from ESI role entry (base, hq, other)."""
    all_roles = set(role_data.get("roles") or [])
    for key in ("roles_at_base", "roles_at_hq", "roles_at_other"):
        all_roles.update(role_data.get(key) or [])
    return all_roles


@app.task
def update_corporation(corporation_id):
    logger.info("Updating corporation %s", corporation_id)
    corporation = EveCorporation.objects.get(corporation_id=corporation_id)
    corporation.populate()
    if corporation.pk is None:
        return
    # fetch and set members if active
    if corporation.active and (corporation.type in ["alliance", "associate"]):
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

        # Populate directors, recruiters, stewards from ESI corporation roles
        esi_roles = EsiClient(corporation.ceo).get_corporation_roles(
            corporation.corporation_id
        )
        if esi_roles.success():
            roles_data = esi_roles.results() or []
            director_ids = []
            recruiter_ids = []
            steward_ids = []
            for entry in roles_data:
                char_id = entry.get("character_id")
                if char_id is None:
                    continue
                all_roles = _all_roles_for_member(entry)
                char, _ = EveCharacter.objects.get_or_create(
                    character_id=char_id, defaults={}
                )
                if "Director" in all_roles:
                    director_ids.append(char.id)
                if "Personnel_Manager" in all_roles:
                    recruiter_ids.append(char.id)
                if "Station_Manager" in all_roles:
                    steward_ids.append(char.id)
            corporation.directors.set(
                EveCharacter.objects.filter(id__in=director_ids)
            )
            corporation.recruiters.set(
                EveCharacter.objects.filter(id__in=recruiter_ids)
            )
            corporation.stewards.set(
                EveCharacter.objects.filter(id__in=steward_ids)
            )


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
def setup_players():
    """Setup EvePlayer entities based on primary character data"""

    created = 0
    # Find characters that are primary via EvePlayer
    for player in EvePlayer.objects.filter(primary_character__isnull=False):
        char = player.primary_character
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
def update_players():
    logger.info("Updating players")
    updated = 0
    deleted = 0
    for player in EvePlayer.objects.all():
        if not player.user:
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

        if player.primary_character:
            new_nickname = player.primary_character.character_name
        else:
            new_nickname = player.user.username

        if player.nickname != new_nickname:
            player.nickname = new_nickname
            player.save()
            updated += 1
            logger.info("Updated EvePlayer nickmame: %s", new_nickname)

    logger.info("EvePlayers updated: %d, deleted: %d", updated, deleted)
