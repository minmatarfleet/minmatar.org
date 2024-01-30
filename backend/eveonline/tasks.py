import logging

from esi.clients import EsiClientProvider
from esi.models import Token

from app.celery import app

from .models import EveCharacter, EveCorporation

esi = EsiClientProvider()
logger = logging.getLogger(__name__)


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
