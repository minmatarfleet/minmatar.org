import logging

from esi.clients import EsiClientProvider

from eveonline.models import EveCharacter, EveCorporation
from eveonline.scopes import MARKET_CHARACTER_SCOPES
from market.helpers import (
    create_character_market_contracts,
    create_corporation_market_contracts,
)

logger = logging.getLogger(__name__)

esi = EsiClientProvider()


def fetch_eve_market_contracts():
    characters = EveCharacter.objects.filter(
        token__scopes__name__in=set(MARKET_CHARACTER_SCOPES),
    ).distinct()

    for character in characters:
        try:
            create_character_market_contracts(character.character_id)
        except Exception as e:
            logger.error(
                f"Failed to fetch character contracts {character.character_id}: {e}"
            )

    corporations = EveCorporation.objects.filter(
        ceo__token__scopes__name__in=set(MARKET_CHARACTER_SCOPES),
        alliance__name__in=[
            "Minmatar Fleet Alliance",
            "Minmatar Fleet Associates",
        ],
    ).distinct()

    for corporation in corporations:
        try:
            create_corporation_market_contracts(corporation.corporation_id)
        except Exception as e:
            logger.error(
                f"Failed to fetch corporation contracts {corporation.corporation_id}: {e}"
            )


def fetch_eve_market_orders():
    pass


def fetch_eve_market_transactions():
    pass
