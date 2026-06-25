"""Tests for fleet member ship snapshot history."""

import factory
from unittest.mock import patch

from django.db.models import signals
from django.utils import timezone

from app.test import TestCase
from eveonline.client import EsiResponse
from fleets.helpers.member_ships import (
    CAPSULE_TYPE_ID,
    apply_esi_fleet_member,
    effective_fleet_ship,
    record_ship_snapshots_for_change,
)
from fleets.models import (
    EveFleet,
    EveFleetAudience,
    EveFleetInstance,
    EveFleetInstanceMember,
    EveFleetInstanceMemberShipSnapshot,
)
from fleets.tests import disconnect_fleet_signals


def _esi_member(
    character_id: int,
    ship_type_id: int,
    *,
    solar_system_id: int = 30000142,
) -> dict:
    return {
        "character_id": character_id,
        "join_time": timezone.now(),
        "role": "squad_member",
        "role_name": "Squad Member",
        "ship_type_id": ship_type_id,
        "solar_system_id": solar_system_id,
        "squad_id": 1,
        "station_id": None,
        "takes_fleet_warp": True,
        "wing_id": 1,
    }


def _resolved_ids(
    character_id: int, ship_type_id: int, ship_name: str
) -> dict:
    return {
        character_id: "Pilot One",
        ship_type_id: ship_name,
        30000142: "Jita",
    }


class FleetMemberShipSnapshotTest(TestCase):
    def setUp(self):
        disconnect_fleet_signals()
        super().setUp()
        self.audience = EveFleetAudience.objects.create(name="Test Audience")
        self.fleet = EveFleet.objects.create(
            audience=self.audience,
            start_time=timezone.now(),
            type="strategic",
            description="Test fleet",
        )
        self.instance = EveFleetInstance.objects.create(
            id=9002,
            eve_fleet=self.fleet,
            start_time=timezone.now(),
        )
        self.member = EveFleetInstanceMember.objects.create(
            eve_fleet_instance=self.instance,
            character_id=12345,
            character_name="Pilot One",
            role="squad_member",
            role_name="Squad Member",
            ship_type_id=22468,
            ship_name="Apocalypse Navy Issue",
            solar_system_id=30000142,
            solar_system_name="Jita",
            squad_id=1,
            wing_id=1,
        )

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    def test_new_member_gets_initial_snapshot(self):
        apply_esi_fleet_member(
            self.instance,
            _esi_member(99999, 22468),
            _resolved_ids(99999, 22468, "Apocalypse Navy Issue"),
        )

        snapshots = EveFleetInstanceMemberShipSnapshot.objects.filter(
            member__character_id=99999
        )
        self.assertEqual(snapshots.count(), 1)
        self.assertEqual(snapshots.get().ship_name, "Apocalypse Navy Issue")

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    def test_repeated_poll_does_not_duplicate_snapshots(self):
        esi_member = _esi_member(12345, 22468)
        resolved = _resolved_ids(12345, 22468, "Apocalypse Navy Issue")

        apply_esi_fleet_member(self.instance, esi_member, resolved)
        apply_esi_fleet_member(self.instance, esi_member, resolved)

        self.assertEqual(
            EveFleetInstanceMemberShipSnapshot.objects.filter(
                member=self.member
            ).count(),
            1,
        )

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    def test_ship_change_records_prior_and_new_ship(self):
        created = record_ship_snapshots_for_change(
            self.member,
            previous_ship_type_id=22468,
            previous_ship_name="Apocalypse Navy Issue",
            previous_solar_system_id=30000142,
            previous_solar_system_name="Jita",
            new_ship_type_id=CAPSULE_TYPE_ID,
            new_ship_name="Capsule",
            new_solar_system_id=30000142,
            new_solar_system_name="Jita",
        )

        self.assertEqual(len(created), 2)
        snapshots = list(
            EveFleetInstanceMemberShipSnapshot.objects.filter(
                member=self.member
            ).order_by("created_at")
        )
        self.assertEqual(
            [snapshot.ship_name for snapshot in snapshots],
            ["Apocalypse Navy Issue", "Capsule"],
        )

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    def test_effective_fleet_ship_uses_last_non_capsule(self):
        record_ship_snapshots_for_change(
            self.member,
            previous_ship_type_id=22468,
            previous_ship_name="Apocalypse Navy Issue",
            previous_solar_system_id=30000142,
            previous_solar_system_name="Jita",
            new_ship_type_id=CAPSULE_TYPE_ID,
            new_ship_name="Capsule",
            new_solar_system_id=30000142,
            new_solar_system_name="Jita",
        )
        self.member.ship_type_id = CAPSULE_TYPE_ID
        self.member.ship_name = "Capsule"
        self.member.save(update_fields=["ship_type_id", "ship_name"])

        ship_type_id, ship_name = effective_fleet_ship(self.member)
        self.assertEqual(ship_type_id, 22468)
        self.assertEqual(ship_name, "Apocalypse Navy Issue")

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    @patch("fleets.models.EsiClient")
    def test_update_fleet_members_records_pod_transition(self, esi_mock):
        esi = esi_mock.return_value
        esi.get_fleet_members.return_value = EsiResponse(
            response_code=200,
            data=[_esi_member(12345, CAPSULE_TYPE_ID)],
        )
        esi.resolve_universe_names.return_value = EsiResponse(
            response_code=200,
            data=[
                {"id": 12345, "name": "Pilot One"},
                {"id": CAPSULE_TYPE_ID, "name": "Capsule"},
                {"id": 30000142, "name": "Jita"},
            ],
        )

        self.instance.boss_id = 12345
        self.instance.save(update_fields=["boss_id"])

        self.instance.update_fleet_members()

        snapshots = list(
            EveFleetInstanceMemberShipSnapshot.objects.filter(
                member=self.member
            ).order_by("created_at")
        )
        self.assertEqual(len(snapshots), 2)
        self.assertEqual(snapshots[-1].ship_name, "Capsule")
        ship_type_id, ship_name = effective_fleet_ship(self.member)
        self.assertEqual(ship_type_id, 22468)
        self.assertEqual(ship_name, "Apocalypse Navy Issue")
