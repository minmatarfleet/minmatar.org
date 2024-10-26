import logging

from esi.clients import EsiClientProvider
from esi.models import Token

from eveonline.models import EveCorporation
from eveonline.scopes import MARKET_CHARACTER_SCOPES
from fittings.models import EveFitting
from market.models import EveMarketContract

esi = EsiClientProvider()
logger = logging.getLogger(__name__)


def create_character_market_contracts(character_id: int):
    token = Token.objects.filter(
        character_id=character_id,
        scopes__name__in=set(MARKET_CHARACTER_SCOPES),
    ).first()

    if not token:
        logger.error(
            f"Character {character_id} does not have required scopes to fetch market contracts."
        )
        return

    contracts = esi.client.Contracts.get_characters_character_id_contracts(
        character_id=character_id, token=token.valid_access_token()
    ).results()

    for contract in contracts:
        fitting = None
        if EveFitting.objects.filter(name=contract["title"]).exists():
            fitting = EveFitting.objects.get(name=contract["title"])
        EveMarketContract.objects.update_or_create(
            id=contract["contract_id"],
            defaults={
                "title": contract["title"],
                "price": contract["price"],
                "assignee_id": contract["assignee_id"],
                "acceptor_id": contract["acceptor_id"],
                "issuer_external_id": contract["issuer_id"],
                "completed_at": contract["date_completed"],
                "fitting_id": fitting.id if fitting else None,
            },
        )
    return


def create_corporation_market_contracts(corporation_id: int):
    corporation = EveCorporation.objects.get(corporation_id=corporation_id)
    if not corporation.ceo:
        logger.error(f"Corporation {corporation_id} does not have a CEO.")
        return

    token = Token.objects.filter(
        character_id=corporation.ceo.character_id,
        scopes__name__in=set(MARKET_CHARACTER_SCOPES),
    ).first()

    if not token:
        logger.error(
            f"Corporation {corporation_id} does not have required scopes to fetch market contracts."
        )
        return

    contracts = esi.client.Contracts.get_corporations_corporation_id_contracts(
        corporation_id=corporation_id, token=token.valid_access_token()
    ).results()

    for contract in contracts:
        fitting = None
        if EveFitting.objects.filter(name=contract["title"]).exists():
            fitting = EveFitting.objects.get(name=contract["title"])
        EveMarketContract.objects.update_or_create(
            id=contract["contract_id"],
            defaults={
                "title": contract["title"],
                "price": contract["price"],
                "assignee_id": contract["assignee_id"],
                "acceptor_id": contract["acceptor_id"],
                "issuer_external_id": contract["issuer_id"],
                "completed_at": contract["date_completed"],
                "fitting_id": fitting.id if fitting else None,
            },
        )
    return
