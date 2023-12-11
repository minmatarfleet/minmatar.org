from app.celery import app
from .models import EveCorporation, EveCharacter
from esi.models import Token
from esi.clients import EsiClientProvider
import logging

esi = EsiClientProvider()
logger = logging.getLogger(__name__)


@app.task
def update_corporations():
    for corporation in EveCorporation.objects.all():
        logger.info(f"Updating corporation {corporation.name}")
        corporation.save()
        if not corporation.active:
            logger.info(
                f"Skipping extra steps for inactive corporation {corporation.name}"
            )
            continue

        logger.info(f"Updating corporation {corporation.name} members")
        for character in EveCharacter.objects.filter(
            corporation_id=corporation.corporation_id
        ):
            logger.info(f"Updating character {character.character_name}")
            character.save()

        logger.info(f"Updating corporation {corporation.name} roster")
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

        logger.info(f"Found {len(esi_corporation_members)} members")
        for character_id in esi_corporation_members:
            if not EveCharacter.objects.filter(
                character_id=character_id
            ).exists():
                logger.info(f"Creating character {character_id}")
                character = EveCharacter.objects.create(
                    character_id=character_id
                )
