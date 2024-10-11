import logging

from esi.clients import EsiClientProvider
from esi.models import Token

from app.celery import app
from eveonline.models import EveCharacter
from freight.models import EveFreightContract
from structures.models import EveStructure

logger = logging.getLogger(__name__)

esi = EsiClientProvider()


@app.task()
def update_contracts():
    """Update freight contracts."""
    logger.info("Updating contracts")
    required_scopes = ["esi-contracts.read_corporation_contracts.v1"]
    token = Token.objects.get(
        scopes__name__in=required_scopes,
        character_id=EveFreightContract.supported_ceo_id,
    )

    contracts_data = (
        esi.client.Contracts.get_corporations_corporation_id_contracts(
            corporation_id=EveFreightContract.supported_corporation_id,
            token=token.valid_access_token(),
        ).results()
    )
    for contract in contracts_data:
        if (
            contract["type"] == EveFreightContract.expected_contract_type
            and contract["status"] in EveFreightContract.tracked_statuses
            and contract["assignee_id"]
            == EveFreightContract.supported_corporation_id
        ):
            start_id = int(contract["start_location_id"])
            end_id = int(contract["end_location_id"])

            start_location = "Unknown"
            if 60000000 < start_id < 61000000:
                system_id = (
                    esi.client.Universe.get_universe_stations_station_id(
                        station_id=start_id
                    ).results()["system_id"]
                )
                system_name = (
                    esi.client.Universe.get_universe_systems_system_id(
                        system_id=system_id
                    ).results()["name"]
                )
                start_location = system_name
            else:
                if EveStructure.objects.filter(id=start_id).exists():
                    start_location = EveStructure.objects.get(id=start_id).name
                else:
                    start_location = "Structure"

            end_location = "Unknown"
            if 60000000 < end_id < 61000000:
                system_id = (
                    esi.client.Universe.get_universe_stations_station_id(
                        station_id=end_id
                    ).results()["system_id"]
                )
                system_name = (
                    esi.client.Universe.get_universe_systems_system_id(
                        system_id=system_id
                    ).results()["name"]
                )
                end_location = system_name
            else:
                if EveStructure.objects.filter(id=end_id).exists():
                    end_location = EveStructure.objects.get(id=end_id).name
                else:
                    end_location = "Structure"

            completed_by = None
            if (
                contract["acceptor_id"]
                != EveFreightContract.supported_corporation_id
            ):
                completed_by_character = EveCharacter.objects.filter(
                    character_id=contract["acceptor_id"]
                ).first()
                if completed_by_character and completed_by_character.token:
                    completed_by = completed_by_character.token.user

            EveFreightContract.objects.update_or_create(
                contract_id=contract["contract_id"],
                defaults={
                    "status": contract["status"],
                    "start_location_name": start_location,
                    "end_location_name": end_location,
                    "volume": contract["volume"],
                    "collateral": contract["collateral"],
                    "reward": contract["reward"],
                    "completed_by": completed_by,
                },
            )
