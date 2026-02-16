import logging

from django.contrib.auth.models import User

from app.celery import app
from eveonline.helpers.characters import (
    update_character_assets as refresh_character_assets,
    update_character_killmails as refresh_character_killmails,
    update_character_skills as refresh_character_skills,
)
from eveonline.models import EveCharacter, EveAlliance

logger = logging.getLogger(__name__)


@app.task(rate_limit="1/m")
def update_character(eve_character_id):
    """Update a character's assets, skills, and killmails."""
    character = EveCharacter.objects.get(character_id=eve_character_id)
    logger.info(
        "Updating character %s (%s)",
        character.character_name,
        eve_character_id,
    )
    refresh_character_assets(eve_character_id)
    refresh_character_skills(eve_character_id)
    refresh_character_killmails(eve_character_id)


@app.task()
def update_character_urgent(eve_character_id):
    """No rate limit for urgent updates."""
    update_character(eve_character_id)


@app.task
def update_alliance_characters():
    """Queue update_character for each alliance character (assets, skills, killmails)."""
    alliance_characters = EveCharacter.objects.filter(
        alliance_id__in=EveAlliance.objects.all().values_list(
            "alliance_id", flat=True
        )
    )
    users_with_alliance_chars = User.objects.filter(
        evecharacter__in=alliance_characters
    ).distinct()
    all_characters = EveCharacter.objects.filter(
        user__in=users_with_alliance_chars
    ).exclude(token=None)

    counter = 0
    for character in all_characters:
        logger.debug("Queuing update for character %s", character.character_id)
        update_character.apply_async(
            args=[character.character_id], countdown=counter % 3600
        )
        counter += 1
