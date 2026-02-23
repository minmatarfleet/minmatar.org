import logging
from datetime import datetime, timedelta
from typing import List

import pytz
from django.db.models import Q
from django.utils import timezone

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


def get_historical_quantity(
    expectation: EveMarketContractExpectation,
) -> List[MarketContractHistoricalQuantity]:
    """Historical finished contract counts for an expectation's fitting (and location)."""
    return get_historical_quantity_for_fitting(
        expectation.fitting, location=expectation.location
    )


def get_historical_quantity_for_fitting(
    fitting: EveFitting,
    location: EveLocation | None = None,
) -> List[MarketContractHistoricalQuantity]:
    """Historical finished contract counts per month for a fitting, optionally at a location."""
    historical_quantity = []
    today = datetime.today()
    utc = pytz.UTC
    for i in range(12):
        month_start = (
            today.replace(day=1, tzinfo=utc) - timedelta(days=i * 30)
        ).replace(day=1)
        month_end = (month_start + timedelta(days=32)).replace(day=1)
        qs = EveMarketContract.objects.filter(
            fitting=fitting,
            status="finished",
            completed_at__gte=month_start,
            completed_at__lt=month_end,
        )
        if location is not None:
            qs = qs.filter(location=location)
        historical_quantity.append(
            MarketContractHistoricalQuantity(
                date=month_start.strftime("%Y-%m-%d"),
                quantity=qs.count(),
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


def _map_contract_status(esi_status: str) -> str:
    """Map ESI contract status to EveMarketContract status_choices."""
    if esi_status in ("outstanding", "in_progress"):
        return "outstanding"
    if esi_status == "finished":
        return "finished"
    if esi_status == "expired":
        return "expired"
    return "outstanding"


def create_or_update_contract_from_db_contract(
    db_contract, location: EveLocation
) -> bool:
    """
    Create or update EveMarketContract from an EveCharacterContract or
    EveCorporationContract. Only stores if type is item_exchange, location
    matches, and title matches a known fitting. Returns True if stored.
    """
    if db_contract.type != EveMarketContract.esi_contract_type:
        logger.info(
            "Skipping contract %s: type %s is not %s",
            db_contract.contract_id,
            db_contract.type,
            EveMarketContract.esi_contract_type,
        )
        return False
    if db_contract.start_location_id != location.location_id:
        logger.info(
            "Skipping contract %s: start_location_id %s does not match location %s",
            db_contract.contract_id,
            db_contract.start_location_id,
            location.location_id,
        )
        return False
    fitting = get_fitting_for_contract(db_contract.title or "")
    if not fitting:
        logger.info(
            "Skipping contract %s: no fitting found for title %r",
            db_contract.contract_id,
            db_contract.title or "",
        )
        return False
    status = _map_contract_status(db_contract.status or "")
    contract, _ = EveMarketContract.objects.get_or_create(
        id=db_contract.contract_id,
        defaults={
            "price": db_contract.price or 0,
            "issuer_external_id": db_contract.issuer_id,
        },
    )
    contract.title = db_contract.title or ""
    contract.status = status
    contract.issued_at = db_contract.date_issued
    contract.expires_at = db_contract.date_expired
    contract.completed_at = db_contract.date_completed
    contract.fitting = fitting
    contract.location = location
    contract.is_public = False
    contract.assignee_id = db_contract.assignee_id
    contract.acceptor_id = db_contract.acceptor_id
    contract.last_updated = timezone.now()
    contract.save()
    return True


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
