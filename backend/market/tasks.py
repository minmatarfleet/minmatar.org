import logging

from django.db.models import Count, Q
from esi.clients import EsiClientProvider

from app.celery import app
from eveonline.models import EveCharacter, EveCorporation
from eveonline.scopes import MARKET_CHARACTER_SCOPES
from market.helpers import (
    create_character_market_contracts,
    create_corporation_market_contracts,
)
from market.models import EveMarketContract

logger = logging.getLogger(__name__)

esi = EsiClientProvider()


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
        logger.info(f"Fetching character contracts {character.character_id}")
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
        .exclude(Q(entity_id__in=known_entity_ids) | Q(entity_id__isnull=True))
        .update(status="expired")
    )


def fetch_eve_market_orders():
    pass


def fetch_eve_market_transactions():
    pass
