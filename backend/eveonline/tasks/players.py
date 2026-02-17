import logging

from esi.models import Token

from app.celery import app
from eveonline.models import EveCharacter, EvePlayer
from eveonline.scopes import scope_group

logger = logging.getLogger(__name__)


@app.task
def fixup_character_tokens():
    """Fix incorrectly linked or identified ESI tokens."""
    for character in EveCharacter.objects.all():
        updated = False

        tokens = Token.objects.filter(character_id=character.character_id)

        if tokens.count() == 1 and not character.token:
            # Character has a single token but it isn't linked, so link it
            character.token = tokens.first()
            updated = True

        if character.token and not getattr(
            character, "esi_scope_groups", None
        ):
            group = scope_group(character.token)
            if group:
                character.esi_scope_groups = [group]
                updated = True

        if updated:
            character.save()


@app.task
def setup_players():
    """Setup EvePlayer entities based on primary character data"""

    created_count = 0
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
            created_count += 1

    logger.info("EvePlayers created: %d", created_count)


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
