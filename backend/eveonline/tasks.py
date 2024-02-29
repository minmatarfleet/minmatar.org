import json
import logging

from esi.clients import EsiClientProvider
from esi.models import Token

from app.celery import app

from .helpers.assets import create_character_assets
from .helpers.skills import create_eve_character_skillset
from .models import EveCharacter, EveCorporation, EveSkillset

esi = EsiClientProvider()
logger = logging.getLogger(__name__)


@app.task
def update_characters():
    for character in EveCharacter.objects.all():
        update_character_skills.apply_async(args=[character.character_id])
        update_character_assets.apply_async(args=[character.character_id])


@app.task
def update_character_skills(eve_character_id):
    required_scopes = ["esi-skills.read_skills.v1"]
    token = Token.objects.filter(
        character_id=eve_character_id, scopes__name__in=required_scopes
    ).first()
    if token is None:
        logger.info(
            "Skipping skills update for character %s", eve_character_id
        )
        return
    esi_skills = esi.client.Skills.get_characters_character_id_skills(
        character_id=eve_character_id, token=token.valid_access_token()
    ).results()
    character = EveCharacter.objects.get(character_id=eve_character_id)
    character.skills_json = json.dumps(esi_skills)
    character.save()
    # update skillsets
    for skillset in EveSkillset.objects.all():
        create_eve_character_skillset(character, skillset)


@app.task
def update_character_assets(eve_character_id):
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
    character = EveCharacter.objects.get(character_id=eve_character_id)
    create_character_assets(character)


@app.task
def update_corporations():
    for corporation in EveCorporation.objects.all():
        logger.info("Updating corporation %s", corporation.name)
        corporation.save()
        if not corporation.active():
            logger.info(
                "Skipping extra steps for inactive corporation %s",
                corporation.name,
            )
            continue

        logger.info("Updating corporation %s characters", corporation.name)
        for character in EveCharacter.objects.filter(
            corporation_id=corporation.corporation_id
        ):
            logger.info("Updating character %s", character.character_name)
            character.save()

        logger.info(
            "Updating corporation %s from external roster", corporation.name
        )
        required_scopes = ["esi-corporations.read_corporation_membership.v1"]
        token = Token.objects.get(
            character_id=corporation.ceo_id, scopes__name__in=required_scopes
        )
        esi_corporation_members = (
            esi.client.Corporation.get_corporations_corporation_id_members(
                corporation_id=corporation.corporation_id,
                token=token.valid_access_token(),
            ).results()
        )

        logger.info("Found %s members", len(esi_corporation_members))
        for character_id in esi_corporation_members:
            if not EveCharacter.objects.filter(
                character_id=character_id
            ).exists():
                logger.info("Creating character %s", character_id)
                character = EveCharacter.objects.create(
                    character_id=character_id
                )
