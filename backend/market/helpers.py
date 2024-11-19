import logging

from django.db.models import Q
from esi.clients import EsiClientProvider
from esi.models import Token

from eveonline.models import EveCorporation
from eveonline.scopes import MARKET_CHARACTER_SCOPES
from fittings.models import EveFitting
from market.models import EveMarketContract, EveMarketLocation

esi = EsiClientProvider()
logger = logging.getLogger(__name__)


def create_market_contract(contract: dict, issuer_id: int) -> None:
    """
    Creates a market contract from ESI data while trusting
    the issuer_id from upstream filtering
    """
    logger.info(
        f"Processing contract {contract['contract_id']}, {contract['title']}"
    )
    if contract["acceptor_id"] == issuer_id:
        logger.info(
            f"Skipping {contract['contract_id']}, issuer is also acceptor."
        )
        return
    if contract["type"] != EveMarketContract.esi_contract_type:
        logger.info(
            f"Skipping {contract['contract_id']}, not an item exchange."
        )
        return

    if not EveMarketLocation.objects.filter(
        location_id=contract["start_location_id"]
    ).exists():
        logger.info(f"Skipping {contract['contract_id']}, location not found.")
        return

    if not EveFitting.objects.filter(
        Q(name=contract["title"]) | Q(aliases__contains=contract["title"])
    ).exists():
        logger.info(f"Skipping {contract['contract_id']}, fitting not found.")
        return

    if (
        EveFitting.objects.filter(
            Q(name=contract["title"]) | Q(aliases__contains=contract["title"])
        ).count()
        > 1
    ):
        logger.info(
            f"Skipping {contract['contract_id']}, unable to determine fitting."
        )
        return

    # Data massaging
    location = EveMarketLocation.objects.get(
        location_id=contract["start_location_id"]
    )
    fitting = EveFitting.objects.get(
        Q(name=contract["title"]) | Q(aliases__contains=contract["title"])
    )
    if contract["status"] == "outstanding":
        status = "outstanding"
    elif contract["status"] == "finished":
        status = "finished"
    else:
        status = "expired"

    contract, _ = EveMarketContract.objects.update_or_create(
        id=contract["contract_id"],
        defaults={
            "title": contract["title"],
            "status": status,
            "price": contract["price"],
            "assignee_id": contract["assignee_id"],
            "acceptor_id": contract["acceptor_id"],
            "issuer_external_id": issuer_id,
            "completed_at": contract["date_completed"],
            "fitting_id": fitting.id,
            "location_id": location.location_id,
        },
    )
    return contract


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

    known_contract_ids = []
    for contract in contracts:
        if (
            contract["for_corporation"]
            and contract["issuer_id"] != character_id
        ):
            continue
        create_market_contract(contract, character_id)
        known_contract_ids.append(contract["contract_id"])

    # Clean up contracts that are no longer in the list
    EveMarketContract.objects.filter(issuer_external_id=character_id).exclude(
        id__in=known_contract_ids
    ).update(status="expired")
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

    known_contract_ids = []
    for contract in contracts:
        if (
            not contract["for_corporation"]
            and contract["issuer_corporation_id"] != corporation_id
        ):
            continue
        create_market_contract(contract, corporation_id)
        known_contract_ids.append(contract["contract_id"])

    # Clean up contracts that are no longer in the list
    EveMarketContract.objects.filter(
        issuer_external_id=corporation_id
    ).exclude(id__in=known_contract_ids).update(status="expired")
    return
