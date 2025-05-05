import logging

from django.db.models import Count, Q
from esi.clients import EsiClientProvider

from app.celery import app
from discord.client import DiscordClient
from eveonline.models import EveCharacter, EveCorporation
from eveonline.scopes import MARKET_CHARACTER_SCOPES
from market.helpers import (
    create_character_market_contracts,
    create_corporation_market_contracts,
)
from market.models import EveMarketContract, EveMarketContractExpectation

logger = logging.getLogger(__name__)

esi = EsiClientProvider()
discord = DiscordClient()

NOTIFICATION_CHANNEL = 1174095138197340300


@app.task()
def fetch_eve_market_contracts():
    known_entity_ids = []
    characters = (
        EveCharacter.objects.annotate(
            matching_scopes=Count(
                "token__scopes",
                filter=Q(token__scopes__name__in=MARKET_CHARACTER_SCOPES),
            )
        )
        .filter(matching_scopes=len(MARKET_CHARACTER_SCOPES))
        .distinct()
    )

    for character in characters:
        if character.esi_suspended:
            logger.info(
                f"Not fetching character contracts for ESI suspended character {character.character_id}"
            )
            continue
        logger.debug(f"Fetching character contracts {character.character_id}")
        try:
            create_character_market_contracts(character.character_id)
            known_entity_ids.append(character.character_id)
        except Exception as e:
            logger.error(
                f"Failed to fetch character contracts {character.character_id}: {e}"
            )

    corporations = (
        EveCorporation.objects.annotate(
            matching_scopes=Count(
                "ceo__token__scopes",
                filter=Q(ceo__token__scopes__name__in=MARKET_CHARACTER_SCOPES),
            )
        )
        .filter(
            matching_scopes=len(MARKET_CHARACTER_SCOPES),
            alliance__name__in=[
                "Minmatar Fleet Alliance",
                "Minmatar Fleet Associates",
            ],
        )
        .distinct()
    )

    for corporation in corporations:
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
