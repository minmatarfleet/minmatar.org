import logging

from bravado.exception import HTTPNotModified

from app.celery import app
from eveonline.client import EsiClient
from eveonline.models import EveCharacter
from freight.models import EveFreightContract
from structures.models import EveStructure

logger = logging.getLogger(__name__)


@app.task()
def update_contracts():
    """Update freight contracts."""
    logger.info("Updating contracts")
    # required_scopes = ["esi-contracts.read_corporation_contracts.v1"]
    # token = Token.get_token(
    #     EveFreightContract.supported_ceo_id, required_scopes
    # )
    # if not token:
    #     logger.error("Unable to get valid EveFreightContract CEO token")
    #     return

    try:
        # contracts_data = (
        #     esi.client.Contracts.get_corporations_corporation_id_contracts(
        #         corporation_id=EveFreightContract.supported_corporation_id,
        #         token=token.valid_access_token(),
        #     ).results()
        # )
        contracts_data = (
            EsiClient(EveFreightContract.supported_ceo_id)
            .get_corporation_contracts(
                EveFreightContract.supported_corporation_id
            )
            .results()
        )
    except HTTPNotModified:
        logger.debug(
            "Contracts not modified for corp %d",
            EveFreightContract.supported_corporation_id,
        )
        return

    contract_ids = set()
    for contract in contracts_data:
        if (
            contract["type"] == EveFreightContract.expected_contract_type
            and contract["status"] in EveFreightContract.tracked_statuses
            and contract["assignee_id"]
            == EveFreightContract.supported_corporation_id
        ):
            contract_ids.add(int(contract["contract_id"]))
            update_contract(contract)

    # Update all hanging contracts
    contracts = EveFreightContract.objects.filter(
        status__in=["outstanding", "in_progress"],
    )
    for contract in contracts:
        if int(contract.contract_id) not in contract_ids:
            contract.status = "expired"
            contract.save()


def update_contract(esi_contract):
    start_id = int(esi_contract["start_location_id"])
    end_id = int(esi_contract["end_location_id"])

    start_location = "Unknown"
    if 60000000 < start_id < 61000000:
        station = EsiClient(None).get_station(start_id)
        start_location = station.eve_solar_system.name
        # system_id = esi.client.Universe.get_universe_stations_station_id(
        #     station_id=start_id
        # ).results()["system_id"]
        # system_name = esi.client.Universe.get_universe_systems_system_id(
        #     system_id=system_id
        # ).results()["name"]
        # start_location = system_name
    else:
        if EveStructure.objects.filter(id=start_id).exists():
            start_location = EveStructure.objects.get(id=start_id).name
        else:
            start_location = "Structure"

    end_location = "Unknown"
    if 60000000 < end_id < 61000000:
        station = EsiClient(None).get_station(end_id)
        end_location = station.eve_solar_system.name
        # system_id = esi.client.Universe.get_universe_stations_station_id(
        #     station_id=end_id
        # ).results()["system_id"]
        # system_name = esi.client.Universe.get_universe_systems_system_id(
        #     system_id=system_id
        # ).results()["name"]
        # end_location = system_name
    else:
        if EveStructure.objects.filter(id=end_id).exists():
            end_location = EveStructure.objects.get(id=end_id).name
        else:
            end_location = "Structure"

    completed_by = None
    if (
        esi_contract["acceptor_id"]
        != EveFreightContract.supported_corporation_id
    ):
        completed_by_character = EveCharacter.objects.filter(
            character_id=esi_contract["acceptor_id"]
        ).first()
        if completed_by_character and completed_by_character.token:
            completed_by = completed_by_character.token.user

    EveFreightContract.objects.update_or_create(
        contract_id=esi_contract["contract_id"],
        defaults={
            "status": esi_contract["status"],
            "start_location_name": start_location,
            "end_location_name": end_location,
            "volume": esi_contract["volume"],
            "collateral": esi_contract["collateral"],
            "reward": esi_contract["reward"],
            "completed_by": completed_by,
            "date_issued": esi_contract["date_issued"],
            "date_completed": esi_contract["date_completed"],
        },
    )
