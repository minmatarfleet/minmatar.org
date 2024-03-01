import json
import logging

from esi.clients import EsiClientProvider
from esi.models import Token
from eveuniverse.models import EveFaction

from app.celery import app

from .helpers.assets import create_character_assets
from .helpers.skills import create_eve_character_skillset
from .models import EveAlliance, EveCharacter, EveCorporation, EveSkillset

esi = EsiClientProvider()
logger = logging.getLogger(__name__)


@app.task
def update_characters():
    for character in EveCharacter.objects.all():
        logger.info("Updating character %s", character.character_id)
        update_character_skills.apply_async(args=[character.character_id])
        update_character_assets.apply_async(args=[character.character_id])


@app.task
def update_character_skills(eve_character_id):
    logger.info("Updating skills for character %s", eve_character_id)
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


@app.task
def update_corporations():
    for corporation in EveCorporation.objects.all():
        update_corporation.apply_async(args=[corporation.corporation_id])


@app.task
def update_corporation(corporation_id):
    logger.info("Updating corporation %s", corporation_id)
    corporation = EveCorporation.objects.get(corporation_id=corporation_id)
    esi_corporation = esi.client.Corporation.get_corporations_corporation_id(
        corporation_id=corporation_id
    ).results()
    logger.info("ESI corporation data: %s", esi_corporation)
    corporation.name = esi_corporation["name"]
    corporation.ticker = esi_corporation["ticker"]
    corporation.member_count = esi_corporation["member_count"]
    # set ceo
    logger.info(
        "Setting CEO as %s for corporation %s",
        esi_corporation["ceo_id"],
        corporation.name,
    )
    corporation.ceo = EveCharacter.objects.get_or_create(
        character_id=esi_corporation["ceo_id"]
    )[0]

    # set alliance
    logger.info("Updating alliance for corporation %s", corporation.name)
    if (
        "alliance_id" in esi_corporation
        and esi_corporation["alliance_id"] is not None
    ):
        logger.info("Setting alliance for corporation %s", corporation.name)
        alliance = EveAlliance.objects.get_or_create(
            alliance_id=esi_corporation["alliance_id"]
        )[0]
        logger.info(
            "Alliance for corporation %s is %s", corporation.name, alliance
        )
        corporation.alliance = alliance
    else:
        corporation.alliance = None
        logger.info("Corporation %s has no alliance", corporation.name)
    # set faction
    logger.info("Updating faction for corporation %s", corporation.name)
    if (
        "faction_id" in esi_corporation
        and esi_corporation["faction_id"] is not None
    ):
        logger.info("Setting faction for corporation %s", corporation.name)
        corporation.faction = EveFaction.objects.get_or_create_esi(
            id=esi_corporation["faction_id"]
        )[0]
    else:
        corporation.faction = None
        logger.info("Corporation %s has no faction", corporation.name)

    corporation.save()
