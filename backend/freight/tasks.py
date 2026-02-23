import logging

from app.celery import app
from eveuniverse.models import EveStation
from eveonline.models import (
    EveCharacter,
    EveCorporation,
    EveCorporationContract,
)
from freight.models import EveFreightContract
from structures.models import EveStructure

logger = logging.getLogger(__name__)


def _resolve_location_name_from_db(location_id):
    """
    Resolve a location ID to a display name using only the database.
    Stations (60M–61M) use EveStation when present; structures use EveStructure.
    """
    if location_id is None:
        return "Unknown"
    loc_id = int(location_id)
    if 60000000 < loc_id < 61000000:
        station = (
            EveStation.objects.filter(id=loc_id)
            .select_related("eve_solar_system")
            .first()
        )
        if station and station.eve_solar_system:
            return station.eve_solar_system.name
        if station:
            return station.name
        return "Unknown"
    structure = EveStructure.objects.filter(id=loc_id).first()
    if structure:
        return structure.name
    return "Structure"


def _create_or_update_freight_contract_from_db(db_contract):
    """Create or update EveFreightContract from an EveCorporationContract."""
    start_location_name = _resolve_location_name_from_db(
        db_contract.start_location_id
    )
    end_location_name = _resolve_location_name_from_db(
        db_contract.end_location_id
    )

    issuer = None
    if db_contract.issuer_id:
        issuer = EveCharacter.objects.filter(
            character_id=db_contract.issuer_id
        ).first()

    completed_by = None
    if db_contract.acceptor_id and (
        db_contract.acceptor_id != EveFreightContract.supported_corporation_id
    ):
        completed_by_character = EveCharacter.objects.filter(
            character_id=db_contract.acceptor_id
        ).first()
        if completed_by_character and getattr(
            completed_by_character, "token", None
        ):
            completed_by = completed_by_character.token.user

    volume = db_contract.volume
    if volume is not None:
        volume = int(volume)
    else:
        volume = 0
    collateral = db_contract.collateral
    if collateral is not None:
        collateral = int(collateral)
    else:
        collateral = 0
    reward = db_contract.reward
    if reward is not None:
        reward = int(reward)
    else:
        reward = 0

    EveFreightContract.objects.update_or_create(
        contract_id=db_contract.contract_id,
        defaults={
            "status": db_contract.status or "outstanding",
            "start_location_name": start_location_name,
            "end_location_name": end_location_name,
            "volume": volume,
            "collateral": collateral,
            "reward": reward,
            "issuer": issuer,
            "completed_by": completed_by,
            "date_issued": db_contract.date_issued,
            "date_completed": db_contract.date_completed,
        },
    )


@app.task()
def update_contracts():
    """
    Update freight contracts from the internal database (EveCorporationContract).
    Does not fetch from ESI; relies on corporation contracts being synced elsewhere.
    """
    logger.info("Updating freight contracts from database")

    corporation = EveCorporation.objects.filter(
        corporation_id=EveFreightContract.supported_corporation_id
    ).first()
    if not corporation:
        logger.warning(
            "Corporation %s not found, skipping freight contract update",
            EveFreightContract.supported_corporation_id,
        )
        return

    db_contracts = EveCorporationContract.objects.filter(
        corporation=corporation,
        type=EveFreightContract.expected_contract_type,
        assignee_id=EveFreightContract.supported_corporation_id,
        status__in=EveFreightContract.tracked_statuses,
    )

    contract_ids = set()
    for db_contract in db_contracts:
        contract_ids.add(db_contract.contract_id)
        _create_or_update_freight_contract_from_db(db_contract)

    logger.info(
        "Stored %s freight contract(s) from database",
        len(contract_ids),
    )

    # Mark outstanding/in_progress contracts not in DB as expired
    expired_count = (
        EveFreightContract.objects.filter(
            status__in=["outstanding", "in_progress"],
        )
        .exclude(contract_id__in=contract_ids)
        .update(status="expired")
    )
    if expired_count:
        logger.info("Expired %s freight contract(s)", expired_count)
