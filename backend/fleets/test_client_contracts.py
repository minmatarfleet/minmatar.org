"""Fleet payloads installed desktop versions render (app/contracts.py).

The desktop's Fleets window reads the upcoming list (/api/fleets/v3), the
fleet window (/api/fleets/window/current and /api/fleets/{id}/window) and
the pilot's recent fleets (/api/fleets/window/mine). One made-up fleet with
a doctrine, a few members and a loss covers the FC and member views.
"""

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase

from app import contracts
from app.testing import make_token
from eveonline.helpers.characters import set_primary_character
from eveonline.models import EveCharacter
from fittings.models import EveDoctrine, EveDoctrineFitting, EveFitting
from fleets.models import (
    EveFleet,
    EveFleetAudience,
    EveFleetInstance,
    EveFleetInstanceMember,
    EveFleetShipVolunteer,
)
from fleets.test_fleet_roles import (
    DAMNATION_EFT,
    DAMNATION_ID,
    DEVOTER_EFT,
    DEVOTER_ID,
    GUARDIAN_EFT,
    GUARDIAN_ID,
)
from fleets.test_fleet_window import AMAMAKE, RIFTER_ID, no_kills
from fleets.tests import disconnect_fleet_signals, setup_fleet_reference_data
from srp.models import EveFleetShipReimbursement
from users.helpers import add_user_permission

FC_CHARACTER, PILOT_CHARACTER = 5000, 1001
LIVE_FLEET, UPCOMING_FLEET = 501, 502


def loss(killmail_id, minutes_ago):
    return {
        "killmail_id": killmail_id,
        "killmail_time": (
            contracts.FIXED_NOW - timedelta(minutes=minutes_ago)
        ).isoformat(),
        "outcome": "loss",
        "solar_system_id": AMAMAKE,
        "solar_system_name": "Amamake",
        "victim_ship_type_id": GUARDIAN_ID,
        "victim_ship_name": "Guardian",
        "victim_character_id": PILOT_CHARACTER,
        "victim_character_name": "Pilot One",
        "isk_value": 250_000_000,
        "fleet_pilots": 4,
        "is_capsule": False,
    }


@patch("fleets.helpers.fleet_window.fleet_kill_report", no_kills)
class FleetContractTests(TestCase):
    def setUp(self):
        cache.clear()
        clock = contracts.frozen_clock()
        clock.start()
        self.addCleanup(clock.stop)
        self.now = contracts.FIXED_NOW
        disconnect_fleet_signals()
        setup_fleet_reference_data()
        self.pilot = self._user(7001, "pilot", PILOT_CHARACTER, "Pilot One")
        self.fc = self._user(7002, "fc", FC_CHARACTER, "The FC")
        doctrine = EveDoctrine.objects.create(
            id=301, name="Armor Damnations", type="non_strategic"
        )
        self.guardian = None
        for pk, name, ship_id, eft in (
            (401, "Damnation", DAMNATION_ID, DAMNATION_EFT),
            (402, "Guardian", GUARDIAN_ID, GUARDIAN_EFT),
            (403, "Devoter", DEVOTER_ID, DEVOTER_EFT),
        ):
            fitting = EveFitting.objects.create(
                id=pk, name=name, ship_id=ship_id, eft_format=eft
            )
            EveDoctrineFitting.objects.create(
                doctrine=doctrine, fitting=fitting, role="primary"
            )
            if name == "Guardian":
                self.guardian = fitting
        audience = EveFleetAudience.objects.get(name="Test Audience")
        self.fleet = EveFleet.objects.create(
            id=LIVE_FLEET,
            type="non_strategic",
            description="Armor roam",
            start_time=self.now - timedelta(minutes=30),
            status="active",
            created_by=self.fc,
            audience=audience,
            doctrine=doctrine,
            location_id=123,
        )
        EveFleet.objects.create(
            id=UPCOMING_FLEET,
            type="training",
            description="Logi class",
            start_time=self.now + timedelta(hours=2),
            status="pending",
            created_by=self.fc,
            audience=audience,
            location_id=123,
        )

    def _user(self, pk, username, character_id, name):
        user = User.objects.create(id=pk, username=username)
        add_user_permission(user, "view_evefleet")
        set_primary_character(
            user,
            EveCharacter.objects.create(
                character_id=character_id, character_name=name, user=user
            ),
        )
        return user

    def _live(self):
        self.instance = EveFleetInstance.objects.create(
            id=900,
            eve_fleet=self.fleet,
            boss_id=FC_CHARACTER,
            last_updated=self.now,
        )
        # start_time is set on create; the fleet formed 25 minutes ago.
        EveFleetInstance.objects.filter(pk=900).update(
            start_time=self.now - timedelta(minutes=25)
        )
        self.instance.refresh_from_db()
        for character_id, ship_id in (
            (FC_CHARACTER, DAMNATION_ID),
            (PILOT_CHARACTER, GUARDIAN_ID),
            (3001, RIFTER_ID),
        ):
            EveFleetInstanceMember.objects.create(
                eve_fleet_instance=self.instance,
                character_id=character_id,
                character_name=f"Pilot {character_id}",
                ship_type_id=ship_id,
                ship_name=f"Ship {ship_id}",
                solar_system_id=AMAMAKE,
                solar_system_name="Amamake",
                squad_id=1,
                wing_id=1,
                join_time=self.now - timedelta(minutes=20),
            )
        EveFleetShipVolunteer.objects.create(
            eve_fleet=self.fleet,
            character_id=PILOT_CHARACTER,
            character_name="Pilot One",
            fitting=self.guardian,
        )

    def _get(self, url, user):
        response = Client().get(
            url, HTTP_AUTHORIZATION=f"Bearer {make_token(user)}"
        )
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def test_upcoming_fleets(self):
        self._live()
        contracts.check(
            self,
            contracts.DESKTOP / "upcoming_fleets.json",
            self._get("/api/fleets/v3?fleet_filter=active", self.pilot),
        )

    def test_fleet_window_member(self):
        self._live()
        contracts.check(
            self,
            contracts.DESKTOP / "fleet_window_member.json",
            self._get("/api/fleets/window/current", self.pilot),
        )

    def test_fleet_window_fc(self):
        self._live()
        contracts.check(
            self,
            contracts.DESKTOP / "fleet_window_fc.json",
            self._get(f"/api/fleets/{LIVE_FLEET}/window", self.fc),
        )

    def test_my_fleets(self):
        self._live()
        EveFleetInstance.objects.filter(pk=900).update(
            end_time=self.now - timedelta(minutes=5)
        )
        report = no_kills(self.fleet)
        report["killmails"] = [loss(77, 15), loss(79, 10)]
        report["ships_lost"] = 2
        EveFleetShipReimbursement.objects.create(
            fleet=self.fleet,
            external_killmail_link="https://zkillboard.com/kill/79/",
            status="approved",
            killmail_id=79,
            character_id=PILOT_CHARACTER,
            character_name="Pilot One",
            primary_character_id=PILOT_CHARACTER,
            primary_character_name="Pilot One",
            amount=42_000_000,
            ship_name="Guardian",
            ship_type_id=GUARDIAN_ID,
        )
        with patch(
            "fleets.helpers.my_fleets.fleet_kill_report", lambda fleet: report
        ):
            payload = self._get("/api/fleets/window/mine", self.pilot)
        contracts.check(self, contracts.DESKTOP / "my_fleets.json", payload)
