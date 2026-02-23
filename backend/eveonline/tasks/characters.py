import logging

from django.contrib.auth.models import User
from esi.models import Token

from app.celery import app
from eveonline.helpers.characters import (
    update_character_assets as refresh_character_assets,
    update_character_blueprints as refresh_character_blueprints,
    update_character_contracts as refresh_character_contracts,
    update_character_industry_jobs as refresh_character_industry_jobs,
    update_character_killmails as refresh_character_killmails,
    update_character_mining as refresh_character_mining,
    update_character_planets as refresh_character_planets,
    update_character_skills as refresh_character_skills,
)
from eveonline.models import EveCharacter, EveAlliance
from eveonline.utils import get_esi_downtime_countdown

logger = logging.getLogger(__name__)

SCOPE_ASSETS = ["esi-assets.read_assets.v1"]
SCOPE_SKILLS = ["esi-skills.read_skills.v1"]
SCOPE_KILLMAILS = ["esi-killmails.read_killmails.v1"]
SCOPE_CONTRACTS = ["esi-contracts.read_character_contracts.v1"]
SCOPE_INDUSTRY_JOBS = ["esi-industry.read_character_jobs.v1"]
SCOPE_MINING = ["esi-industry.read_character_mining.v1"]
SCOPE_PLANETS = ["esi-planets.manage_planets.v1"]
SCOPE_BLUEPRINTS = ["esi-characters.read_blueprints.v1"]


@app.task(rate_limit="1/m")
def update_character(eve_character_id):
    """Update a character's assets, skills, killmails, contracts, and industry jobs."""
    countdown = get_esi_downtime_countdown()
    if countdown > 0:
        update_character.apply_async(
            args=[eve_character_id],
            countdown=countdown,
        )
        logger.info(
            "Deferring character update for %s by %s s (ESI downtime 11:00–11:15 UTC)",
            eve_character_id,
            countdown,
        )
        return

    character = EveCharacter.objects.get(character_id=eve_character_id)
    logger.info(
        "Updating character %s (%s)",
        character.character_name,
        eve_character_id,
    )
    if character.esi_suspended:
        logger.info(
            "Skipping update for ESI suspended character %s",
            eve_character_id,
        )
        return
    if Token.get_token(eve_character_id, SCOPE_ASSETS):
        refresh_character_assets(eve_character_id)
    if Token.get_token(eve_character_id, SCOPE_SKILLS):
        refresh_character_skills(eve_character_id)
    if Token.get_token(eve_character_id, SCOPE_KILLMAILS):
        refresh_character_killmails(eve_character_id)
    if Token.get_token(eve_character_id, SCOPE_CONTRACTS):
        refresh_character_contracts(eve_character_id)
    if Token.get_token(eve_character_id, SCOPE_INDUSTRY_JOBS):
        refresh_character_industry_jobs(eve_character_id)
    if Token.get_token(eve_character_id, SCOPE_MINING):
        refresh_character_mining(eve_character_id)
    if Token.get_token(eve_character_id, SCOPE_PLANETS):
        refresh_character_planets(eve_character_id)
    if Token.get_token(eve_character_id, SCOPE_BLUEPRINTS):
        refresh_character_blueprints(eve_character_id)


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

    logger.info(
        "Queuing update_character for %d alliance character(s)",
        all_characters.count(),
    )
    for character in all_characters:
        update_character.apply_async(args=[character.character_id])
