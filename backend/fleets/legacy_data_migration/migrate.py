from django.contrib.auth.models import Group

from eveonline.models import EveCharacter
from fittings.models import EveDoctrine
from fleets.legacy_data_migration.doctrines import doctrines as doctrine_data
from fleets.legacy_data_migration.esi_fleet_members import (
    esi_fleet_members as esi_fleet_member_data,
)
from fleets.legacy_data_migration.esi_fleets import (
    esi_fleets as esi_fleet_data,
)
from fleets.legacy_data_migration.fleets import fleets as fleet_data
from fleets.models import EveFleet, EveFleetInstance, EveFleetInstanceMember

doctrine_lookup = {}
fleet_instance_lookup = {}
fleet_instance_members_lookup = {}


def parse_doctrines():
    for doctrine in doctrine_data:
        doctrine_obj = EveDoctrine.objects.filter(
            name=doctrine["fields"]["name"]
        ).first()
        if doctrine_obj:
            doctrine_lookup[doctrine["pk"]] = doctrine_obj


def parse_fleet_instances():
    for fleet_instance in esi_fleet_data:
        fleet_instance_lookup[fleet_instance["fields"]["fleet"]] = (
            fleet_instance
        )


def parse_fleet_instance_members():
    for fleet_instance_member in esi_fleet_member_data:
        # set to empty array if unknown yet
        if (
            fleet_instance_member["fields"]["fleet"]
            not in fleet_instance_members_lookup
        ):
            fleet_instance_members_lookup[
                fleet_instance_member["fields"]["fleet"]
            ] = []

        fleet_instance_members_lookup[
            fleet_instance_member["fields"]["fleet"]
        ].append(fleet_instance_member)


def get_audience(fleet):
    try:
        if "militia" in fleet["fields"]["audience"]:
            return Group.objects.get(name="Militia")
        elif "alliance" in fleet["fields"]["audience"]:
            return Group.objects.get(name="Alliance")
        else:
            return Group.objects.get(name="Alliance")
    except Group.DoesNotExist:
        return Group.objects.all()[0]


def get_doctrine(fleet):
    if "doctrine_id" not in fleet["fields"]:
        return None
    if fleet["fields"]["doctrine_id"] in doctrine_lookup:
        return doctrine_lookup[fleet["fields"]["doctrine_id"]]
    return None


def migrate():
    parse_doctrines()
    parse_fleet_instances()
    parse_fleet_instance_members()

    for fleet in fleet_data:
        fleet_commander = EveCharacter.objects.filter(
            character_id=fleet["fields"]["fleet_commander_id"]
        ).first()
        if not fleet_commander:
            continue
        if not fleet_commander.token:
            continue

        eve_fleet = EveFleet.objects.create(
            description=(
                fleet["fields"]["description"]
                if "description" in fleet["fields"]
                and fleet["fields"]["description"]
                else "Placeholder description"
            ),
            type=fleet["fields"]["type"],
            start_time=fleet["fields"]["start_time"],
            created_by=fleet_commander.token.user,
            audience=get_audience(fleet),
            doctrine=get_doctrine(fleet),
            location=None,
        )

        fleet_instance = fleet_instance_lookup.get(fleet["pk"])
        if not fleet_instance:
            print("skipping fleet instance")
            continue

        fleet_instance_obj = EveFleetInstance.objects.create(
            id=fleet_instance["pk"],
            eve_fleet=eve_fleet,
            start_time=fleet_instance["fields"]["start_time"],
            end_time=fleet_instance["fields"]["end_time"],
        )

        fleet_instance_members = fleet_instance_members_lookup.get(
            fleet_instance_obj.id
        )

        if not fleet_instance_members:
            print("skipping fleet instance members")
            continue

        for fleet_instance_member in fleet_instance_members:
            EveFleetInstanceMember.objects.create(
                eve_fleet_instance=fleet_instance_obj,
                character_id=fleet_instance_member["fields"]["character_id"],
                character_name=fleet_instance_member["fields"][
                    "character_name"
                ],
                join_time=fleet_instance_member["fields"]["join_time"],
                role=fleet_instance_member["fields"]["role"],
                role_name=fleet_instance_member["fields"]["role_name"],
                ship_type_id=fleet_instance_member["fields"]["ship_type_id"],
                ship_name=fleet_instance_member["fields"]["ship_name"],
                solar_system_id=fleet_instance_member["fields"][
                    "solar_system_id"
                ],
                solar_system_name=fleet_instance_member["fields"][
                    "solar_system_name"
                ],
                squad_id=fleet_instance_member["fields"]["squad_id"],
                station_id=fleet_instance_member["fields"]["station_id"],
                takes_fleet_warp=fleet_instance_member["fields"][
                    "takes_fleet_warp"
                ],
                wing_id=fleet_instance_member["fields"]["wing_id"],
            )
