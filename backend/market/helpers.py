import logging
from datetime import datetime, timedelta
from typing import List

import pytz
from django.db.models import Q
from esi.clients import EsiClientProvider
from esi.models import Token
from eveonline.client import EsiClient

from eveonline.models import EveCorporation
from eveonline.scopes import MARKET_CHARACTER_SCOPES
from fittings.models import EveFitting
from market.models import (
    EveMarketContract,
    EveMarketContractExpectation,
    EveMarketLocation,
)

esi = EsiClientProvider()
logger = logging.getLogger(__name__)

# pylint: disable=W1405


class MarketContractHistoricalQuantity:
    date: str
    quantity: int

    def __init__(self, date: str, quantity: int):
        self.date = date
        self.quantity = quantity


def create_market_contract(contract: dict, issuer_id: int) -> None:
    """
    Creates a market contract from ESI data while trusting
    the issuer_id from upstream filtering
    """
    # Need to add comma for ships that contain same name
    # e.g Exequror and Exequror Navy Issue
    alias_title_lookup = f"{contract['title']},"
    logger.debug(
        f"Processing contract {contract['contract_id']}, {contract['title']}"
    )
    if contract["acceptor_id"] == issuer_id:
        logger.debug(
            f"Skipping {contract['contract_id']}, issuer is also acceptor."
        )
        return
    if contract["type"] != EveMarketContract.esi_contract_type:
        logger.debug(
            f"Skipping {contract['contract_id']}, not an item exchange."
        )
        return

    if not EveMarketLocation.objects.filter(
        location_id=contract["start_location_id"]
    ).exists():
        logger.info(
            "Skipping %s, location not found, %s",
            contract["contract_id"],
            contract["start_location_id"],
        )
        return

    if not EveFitting.objects.filter(
        Q(name=contract["title"]) | Q(aliases__contains=alias_title_lookup)
    ).exists():
        logger.info(
            "Skipping %s, fitting not found, %s",
            contract["contract_id"],
            contract["title"],
        )
        return

    if (
        EveFitting.objects.filter(
            Q(name=contract["title"]) | Q(aliases__contains=alias_title_lookup)
        ).count()
        > 1
    ):
        logger.info(
            "Skipping %s, unable to determine fitting, %s",
            contract["contract_id"],
            contract["title"],
        )
        return

    # Data massaging
    location = EveMarketLocation.objects.get(
        location_id=contract["start_location_id"]
    )
    fitting = EveFitting.objects.get(
        Q(name=contract["title"]) | Q(aliases__contains=alias_title_lookup)
    )
    if contract["status"] == "outstanding":
        status = "outstanding"
    elif contract["status"] == "finished":
        status = "finished"
    else:
        status = "expired"

    logger.info(
        "Processing contract %s, %s in %s (%s)",
        contract["contract_id"],
        contract["title"],
        contract["start_location_id"],
        contract["status"],
    )

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
    logger.debug("Contract %d created", contract["contract_id"])
    return contract


def create_character_market_contracts(character_id: int):
    # token = Token.get_token(character_id, MARKET_CHARACTER_SCOPES)
    # if not token:
    #     logger.error(
    #         f"Character {character_id} does not have required scopes to fetch market contracts."
    #     )
    #     return

    # contracts = esi.client.Contracts.get_characters_character_id_contracts(
    #     character_id=character_id, token=token.valid_access_token()
    # ).results()

    response = EsiClient(character_id).get_character_contracts()
    if not response.success:
        logger.error(
            "Error %d getting contracts for %s.",
            response.response_code,
            character_id,
        )
        return
    contracts = response.data

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
    if corporation.ceo.esi_suspended:
        logger.warning(f"Corporation {corporation_id} CEO has ESI suspended.")
        return

    token = Token.get_token(
        corporation.ceo.character_id, MARKET_CHARACTER_SCOPES
    )

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


def get_historical_quantity(
    expectation: EveMarketContractExpectation,
) -> List[MarketContractHistoricalQuantity]:
    """
    Returns the historical quantity for an expectation
    """
    historical_quantity = []
    today = datetime.today()
    utc = pytz.UTC
    for i in range(12):
        month_start = (
            today.replace(day=1, tzinfo=utc) - timedelta(days=i * 30)
        ).replace(day=1)
        month_end = (month_start + timedelta(days=32)).replace(day=1)
        historical_quantity.append(
            MarketContractHistoricalQuantity(
                date=month_start.strftime("%Y-%m-%d"),
                quantity=EveMarketContract.objects.filter(
                    fitting=expectation.fitting,
                    status="finished",
                    completed_at__gte=month_start,
                    completed_at__lt=month_end,
                ).count(),
            )
        )

    return historical_quantity
