import logging
from datetime import datetime, timedelta
from typing import List

import pytz
from django.db.models import Q
from django.utils import timezone

from eveonline.client import EsiClient
from eveonline.models import EveCharacter, EveCorporation, EveLocation
from fittings.models import EveFitting

from market.models import (
    EveMarketContract,
    EveMarketContractError,
    EveMarketContractExpectation,
)

logger = logging.getLogger(__name__)

# pylint: disable=W1405


class MarketContractHistoricalQuantity:
    date: str
    quantity: int

    def __init__(self, date: str, quantity: int):
        self.date = date
        self.quantity = quantity


def create_market_contract(contract: dict, issuer_id: int) -> None:
    # Need to add comma for ships that contain same name
    # e.g Exequror and Exequror Navy Issue
    alias_title_lookup = f"{contract['title']},"
    logger.debug(
        f"Processing contract {contract['contract_id']}, {contract['title']}"
    )
    if contract["acceptor_id"] == issuer_id:
        logger.debug(
            f"Skipping contract {contract['contract_id']}, issuer is also acceptor."
        )
        return
    if contract["type"] != EveMarketContract.esi_contract_type:
        logger.debug(
            f"Skipping contract {contract['contract_id']}, not an item exchange."
        )
        return

    if not EveLocation.objects.filter(
        location_id=contract["start_location_id"]
    ).exists():
        logger.info(
            "Skipping contract %s, location not found, %s",
            contract["contract_id"],
            contract["start_location_id"],
        )
        return

    if not EveFitting.objects.filter(
        Q(name=contract["title"]) | Q(aliases__contains=alias_title_lookup)
    ).exists():
        logger.info(
            "Skipping contract %s, fitting not found, %s",
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
            "Skipping contract %s, unable to determine fitting, %s",
            contract["contract_id"],
            contract["title"],
        )
        return

    # Data massaging
    location = EveLocation.objects.get(
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
        "Updating contract %s, %s in %s (%s)",
        contract["contract_id"],
        contract["title"],
        contract["start_location_id"],
        contract["status"],
    )

    contract_instance, _ = EveMarketContract.objects.update_or_create(
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
    return contract_instance


def create_character_market_contracts(character_id: int):
    response = EsiClient(character_id).get_character_contracts()
    if not response.success():
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


def create_corporation_market_contracts(
    corporation_id: int, character_id: int | None = None
):
    """
    Fetch and sync market contracts for a corporation.

    Uses character_id for the ESI token if provided; otherwise uses the
    corporation's CEO. Caller should pass a character that has a valid token
    with esi-contracts.read_corporation_contracts.v1 and is in the corporation.
    """
    corporation = EveCorporation.objects.get(corporation_id=corporation_id)
    token_character_id = character_id
    if token_character_id is None:
        if not corporation.ceo:
            logger.error(f"Corporation {corporation_id} does not have a CEO.")
            return
        token_character_id = corporation.ceo.character_id

    response = EsiClient(token_character_id).get_corporation_contracts(
        corporation_id
    )

    if not response.success():
        logger.error(
            f"Error fetching contracts for corporation {corporation_id} ({response.response_code})"
        )
        return

    known_contract_ids = []
    for contract in response.results():
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


# In-memory cache for get_fitting_for_contract (public contract title -> fitting)
fitting_cache = {}


def get_fitting_for_contract(contract_summary: str) -> EveFitting | None:
    if contract_summary is None or contract_summary.strip() == "":
        return None

    if contract_summary in fitting_cache:
        return fitting_cache[contract_summary]

    contract_summary = contract_summary.replace("[FLEET]", "[FL33T]")

    fitting = None

    possible_matches = EveFitting.objects.filter(
        Q(name__iexact=contract_summary)
        | Q(aliases__contains=contract_summary)
    )

    for candidate in possible_matches:
        if candidate.name.lower() == contract_summary.lower():
            fitting = candidate
            break
        for alias in candidate.aliases.lower().split(","):
            if alias == contract_summary.lower():
                fitting = candidate
                break

    if not fitting:
        return None

    fitting_cache[contract_summary] = fitting
    return fitting


def create_or_update_contract(esi_contract, location: EveLocation):
    if not esi_contract["type"] == EveMarketContract.esi_contract_type:
        return
    if not esi_contract["start_location_id"] == location.location_id:
        return

    fitting = get_fitting_for_contract(esi_contract["title"])
    if not fitting:
        record_unmatched_contract(esi_contract, location)
        return

    contract, _ = EveMarketContract.objects.get_or_create(
        id=esi_contract["contract_id"],
        defaults={
            "price": esi_contract["price"],
            "issuer_external_id": esi_contract["issuer_id"],
        },
    )
    contract.title = esi_contract["title"]
    contract.status = "outstanding"
    contract.issued_at = esi_contract["date_issued"]
    contract.expires_at = esi_contract["date_expired"]
    contract.fitting = fitting
    contract.location = location
    contract.is_public = True
    contract.last_updated = timezone.now()
    contract.save()


def record_unmatched_contract(esi_contract, location: EveLocation):
    logger.info(
        "Ignoring public contract %d, unknown fitting: %s",
        esi_contract["contract_id"],
        esi_contract["title"],
    )
    char = EveCharacter.objects.filter(
        character_id=esi_contract["issuer_id"]
    ).first()
    corp = (
        EveCorporation.objects.filter(corporation_id=char.corporation_id)
        .select_related("alliance")
        .first()
        if char and char.corporation_id
        else None
    )
    if corp and corp.alliance and corp.alliance.ticker in ["FL33T", "BUILD"]:
        contract_error, created = EveMarketContractError.objects.get_or_create(
            location=location,
            issuer=char,
            title=esi_contract["title"],
            defaults={
                "quantity": 1,
            },
        )
        if not created:
            contract_error.quantity += 1
            contract_error.save()


def update_completed_contracts(cutoff: datetime) -> int:
    updated = (
        EveMarketContract.objects.filter(status="outstanding")
        .filter(is_public=True)
        .filter(expires_at__gt=cutoff)
        .filter(last_updated__lt=cutoff)
        .update(status="finished")
    )
    logger.info("Set %d public contracts to finished status", updated)
    return updated


def update_expired_contracts(cutoff: datetime) -> int:
    updated = (
        EveMarketContract.objects.filter(status="outstanding")
        .filter(is_public=True)
        .filter(expires_at__lt=cutoff)
        .update(status="expired")
    )
    logger.info("Set %d public contracts to expired status", updated)
    return updated
