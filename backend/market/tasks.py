import logging

from django.db.models import Q
from esi.models import Token

from app.celery import app
from discord.client import DiscordClient
from eveonline.models import EveCharacter, EveCorporation
from market.helpers import (
    create_character_market_contracts,
    create_corporation_market_contracts,
)
from market.models import EveMarketContract, EveMarketContractExpectation

logger = logging.getLogger(__name__)

discord = DiscordClient()

NOTIFICATION_CHANNEL = 1174095138197340300


@app.task()
def fetch_eve_market_contracts():
    known_entity_ids = []
    characters = EveCharacter.objects.exclude(token__isnull=True)

    for character in characters:
        if character.esi_suspended:
            logger.info(
                f"Not fetching character contracts for ESI suspended character {character.character_id}"
            )
            continue
        required_scopes = ["esi-contracts.read_character_contracts.v1"]
        if not Token.get_token(character.character_id, required_scopes):
            continue

        logger.debug(f"Fetching character contracts {character.character_id}")
        try:
            create_character_market_contracts(character.character_id)
            known_entity_ids.append(character.character_id)
        except Exception as e:
            logger.error(
                f"Failed to fetch character contracts {character.character_id}: {e}"
            )

    corporations = EveCorporation.objects.filter(
        alliance__name__in=[
            "Minmatar Fleet Alliance",
            "Minmatar Fleet Associates",
        ],
    ).distinct()

    for corporation in corporations:
        required_scopes = ["esi-contracts.read_corporation_contracts.v1"]
        if not Token.get_token(corporation.ceo.character_id, required_scopes):
            continue

        logger.info(
            f"Fetching corporation contracts {corporation.corporation_id}"
        )
        try:
            create_corporation_market_contracts(corporation.corporation_id)
            known_entity_ids.append(corporation.corporation_id)
        except Exception as e:
            logger.error(
                f"Failed to fetch corporation contracts {corporation.corporation_id}: {e}"
            )

    # Expire any outstanding contracts that are not associated with known entities
    (
        EveMarketContract.objects.filter(status="outstanding")
        .exclude(
            Q(issuer_external_id__in=known_entity_ids)
            | Q(issuer_external_id__isnull=True)
        )
        .update(status="expired")
    )


def fetch_eve_market_orders():
    pass


def fetch_eve_market_transactions():
    pass


@app.task()
def notify_eve_market_contract_warnings():
    message = "The following contracts are understocked:\n"
    for expectation in EveMarketContractExpectation.objects.all():
        if expectation.is_understocked:
            message += f"**{expectation.fitting.name}** ({expectation.current_quantity}/{expectation.desired_quantity})\n"

    discord.create_message(channel_id=NOTIFICATION_CHANNEL, message=message)
