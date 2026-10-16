"""Fleet roles from ships: fit classification, burst picks, coverage."""

from datetime import timedelta

from django.contrib.auth.models import User
from django.test import Client, SimpleTestCase
from django.utils import timezone

from app.test import TestCase
from eveonline.models import EveCharacter
from fittings.models import EveDoctrine, EveDoctrineFitting, EveFitting
from fleets.helpers.eft_items import parse_eft_items
from fleets.helpers.fit_roles import fit_roles
from fleets.models import (
    EveFleetInstance,
    EveFleetInstanceMember,
    EveFleetRoleVolunteer,
    EveFleetShipVolunteer,
    _motd_role_volunteers,
)
from fleets.test_ship_volunteers_refits import token_for
from fleets.tests import (
    BASE_URL,
    disconnect_fleet_signals,
    make_test_fleet,
    setup_fleet_reference_data,
)
from users.helpers import add_user_permission

# Production doctrine fit 177, verbatim apart from trimmed cargo.
DAMNATION_EFT = """[Damnation, [FL33T] 3X/4X Damnation]

Damage Control II
Imperial Navy 1600mm Steel Plates

50MN Quad LiF Restrained Microwarpdrive
Sensor Booster II

Armor Command Burst II /offline
Armor Command Burst II /offline
Armor Command Burst II /offline
Skirmish Command Burst II /offline
Skirmish Command Burst II
Information Command Burst II
Information Command Burst II

Medium Trimark Armor Pump II


Acolyte II x5

Information Command Burst II x1
Skirmish Command Burst II x1
"""

GUARDIAN_EFT = """[Guardian, [FL33T] Guardian]
Damage Control II

Large Remote Armor Repairer II
Large Remote Armor Repairer II
Large Inductive Compact Remote Capacitor Transmitter
"""

MYRMIDON_EFT = """[Myrmidon, Pointrunner Myrmidon]
Medium Remote Armor Repairer II
Armor Command Burst I
"""

ZARMAZD_EFT = """[Zarmazd, 50mn Zarmazd]
Perun Heavy Mutadaptive Remote Armor Repairer
"""

DEVOTER_EFT = """[Devoter, Devoter]
Warp Disruption Field Generator II
Cynosural Field Generator I
"""

DAMNATION_ID = 22474
GUARDIAN_ID = 11987
DEVOTER_ID = 12017


class FitRolesTestCase(SimpleTestCase):
    def test_damnation_runs_its_online_bursts_and_can_switch(self):
        roles = fit_roles(DAMNATION_EFT, "Command Ship")

        self.assertEqual(3, roles.burst_slots)
        self.assertEqual(
            ["skirmish", "information", "information"],
            roles.default_bursts(),
        )
        # Spares in cargo are not counted as fitted.
        self.assertEqual(
            {"armor": 3, "skirmish": 2, "information": 2},
            roles.bursts_fitted,
        )
        self.assertIsNone(roles.validate_bursts(["armor"] * 3))
        self.assertIsNone(roles.validate_bursts(["skirmish"]))
        self.assertIn("runs 3", roles.validate_bursts(["armor"] * 4))
        self.assertIn(
            "Only 2 Skirmish", roles.validate_bursts(["skirmish"] * 3)
        )
        self.assertIn("Only 0 Shield", roles.validate_bursts(["shield"]))

    def test_logi_needs_two_remote_modules_or_a_logi_hull(self):
        self.assertTrue(fit_roles(GUARDIAN_EFT, "Logistics").logi)
        self.assertTrue(fit_roles(ZARMAZD_EFT, "Logistics").logi)
        self.assertFalse(fit_roles(ZARMAZD_EFT, "Cruiser").logi)
        brawler = fit_roles(MYRMIDON_EFT, "Combat Battlecruiser")
        self.assertFalse(brawler.logi)
        self.assertEqual(["armor"], brawler.default_bursts())

    def test_cyno(self):
        self.assertTrue(fit_roles(DEVOTER_EFT).cyno)
        self.assertFalse(fit_roles(GUARDIAN_EFT).cyno)

    def test_non_links_fit_rejects_bursts(self):
        roles = fit_roles(GUARDIAN_EFT, "Logistics")
        self.assertIsNone(roles.validate_bursts([]))
        self.assertIsNotNone(roles.validate_bursts(["armor"]))

    def test_parser_strips_offline_so_the_module_resolves(self):
        items = [i for i in parse_eft_items(DAMNATION_EFT) if not i.stacked]
        bursts = [i for i in items if "Command Burst" in i.name]
        self.assertEqual(7, len(bursts))
        self.assertTrue(all(not i.name.endswith("/offline") for i in bursts))
        self.assertEqual(4, sum(1 for i in bursts if i.offline))


class FleetRolesRouterTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        disconnect_fleet_signals()
        setup_fleet_reference_data()
        super().setUp()
        add_user_permission(self.user, "view_evefleet")
        self.auth = {"HTTP_AUTHORIZATION": f"Bearer {self.token}"}
        EveCharacter.objects.create(
            character_id=1001, character_name="Pilot One", user=self.user
        )
        EveCharacter.objects.create(
            character_id=1002, character_name="Pilot Two", user=self.user
        )
        self.doctrine = EveDoctrine.objects.create(
            name="Armor", type="non_strategic", description=""
        )
        self.damnation = self._doctrine_fit(
            "[FL33T] 3X/4X Damnation", DAMNATION_ID, DAMNATION_EFT, "support"
        )
        self.guardian = self._doctrine_fit(
            "[FL33T] Guardian", GUARDIAN_ID, GUARDIAN_EFT, "support"
        )
        self.devoter = self._doctrine_fit(
            "Devoter", DEVOTER_ID, DEVOTER_EFT, "support"
        )
        self.fc_user = User.objects.create(username="fc")
        self.fleet = make_test_fleet("Fleet", self.fc_user)
        self.fleet.doctrine = self.doctrine
        self.fleet.save()

    def _doctrine_fit(self, name, ship_id, eft, role):
        fitting = EveFitting.objects.create(
            name=name, ship_id=ship_id, description="", eft_format=eft
        )
        EveDoctrineFitting.objects.create(
            doctrine=self.doctrine, fitting=fitting, role=role
        )
        return fitting

    def _put(self, *selections):
        return self.client.put(
            f"{BASE_URL}/{self.fleet.id}/my-ship-volunteers",
            {"selections": list(selections)},
            "application/json",
            **self.auth,
        )

    def _roles(self, auth=None):
        response = self.client.get(
            f"{BASE_URL}/{self.fleet.id}/roles", **(auth or self.auth)
        )
        self.assertEqual(200, response.status_code, response.content)
        return response.json()

    @staticmethod
    def _links(body):
        return {
            row["kind"]: [
                (p["character_name"], p["count"]) for p in row["pilots"]
            ]
            for row in body["links"]
        }

    def test_volunteering_a_links_ship_defaults_to_its_online_bursts(self):
        response = self._put(
            {"character_id": 1001, "fitting_id": self.damnation.id}
        )

        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(
            ["skirmish", "information", "information"],
            response.json()[0]["bursts"],
        )
        links = self._links(self._roles())
        self.assertEqual([("Pilot One", 1)], links["skirmish"])
        self.assertEqual([("Pilot One", 2)], links["information"])
        self.assertEqual([], links["armor"])

    def test_pilot_switches_to_armor_links(self):
        response = self._put(
            {
                "character_id": 1001,
                "fitting_id": self.damnation.id,
                "bursts": ["armor", "armor", "armor"],
            }
        )

        self.assertEqual(200, response.status_code, response.content)
        links = self._links(self._roles())
        self.assertEqual([("Pilot One", 3)], links["armor"])
        self.assertEqual([], links["skirmish"])

    def test_bursts_beyond_the_fit_are_rejected(self):
        response = self._put(
            {
                "character_id": 1001,
                "fitting_id": self.damnation.id,
                "bursts": ["armor"] * 4,
            }
        )
        self.assertEqual(400, response.status_code)
        response = self._put(
            {
                "character_id": 1001,
                "fitting_id": self.guardian.id,
                "bursts": ["armor"],
            }
        )
        self.assertEqual(400, response.status_code)
        self.assertFalse(EveFleetShipVolunteer.objects.exists())

    def test_cyno_and_logi_ships_fill_those_roles(self):
        self._put(
            {"character_id": 1001, "fitting_id": self.devoter.id},
            {"character_id": 1002, "fitting_id": self.guardian.id},
        )

        body = self._roles()
        self.assertEqual(
            ["Pilot One"], [p["character_name"] for p in body["cynos"]]
        )
        self.assertEqual(
            ["Pilot Two"], [p["character_name"] for p in body["logi"]]
        )
        cynos = dict(_motd_role_volunteers(self.fleet))["Cynos"]
        self.assertEqual([(1001, "Pilot One")], cynos)

    def test_resaving_the_same_ship_keeps_the_cyno_system(self):
        self._put({"character_id": 1001, "fitting_id": self.devoter.id})
        EveFleetShipVolunteer.objects.update(
            solar_system_id=30003070, solar_system_name="Sosala"
        )

        self._put({"character_id": 1001, "fitting_id": self.devoter.id})
        self.assertEqual(
            "Sosala", EveFleetShipVolunteer.objects.get().solar_system_name
        )

        self._put({"character_id": 1001, "fitting_id": self.guardian.id})
        self.assertEqual(
            "", EveFleetShipVolunteer.objects.get().solar_system_name
        )

    def _in_fleet(self, character_id, name, ship_type_id, seen_ago):
        instance, _ = EveFleetInstance.objects.get_or_create(
            id=7001, defaults={"eve_fleet": self.fleet}
        )
        EveFleetInstance.objects.filter(pk=instance.pk).update(
            last_updated=timezone.now()
        )
        member = EveFleetInstanceMember.objects.create(
            eve_fleet_instance=instance,
            character_id=character_id,
            character_name=name,
            role="squad_member",
            role_name="Squad Member",
            ship_type_id=ship_type_id,
            ship_name="",
            solar_system_id=30002537,
            solar_system_name="Amamake",
            squad_id=1,
            wing_id=1,
        )
        EveFleetInstanceMember.objects.filter(pk=member.pk).update(
            updated_at=timezone.now() - seen_ago
        )

    def test_ships_in_fleet_fill_roles_without_volunteering(self):
        self._in_fleet(3001, "Fleet Damnation", DAMNATION_ID, timedelta(0))
        # Left the fleet an hour ago: no longer counted.
        self._in_fleet(3002, "Gone Guardian", GUARDIAN_ID, timedelta(hours=1))

        body = self._roles()
        links = self._links(body)
        self.assertEqual([("Fleet Damnation", 2)], links["information"])
        self.assertEqual([], body["logi"])
        info = next(r for r in body["links"] if r["kind"] == "information")
        self.assertEqual("in_fleet", info["pilots"][0]["source"])

    def test_the_ship_in_fleet_wins_over_the_volunteered_one(self):
        self._put({"character_id": 1001, "fitting_id": self.devoter.id})
        self._in_fleet(1001, "Pilot One", GUARDIAN_ID, timedelta(0))

        body = self._roles()
        self.assertEqual([], body["cynos"])
        self.assertEqual(
            ["Pilot One"], [p["character_name"] for p in body["logi"]]
        )

    def test_volunteered_bursts_are_kept_once_in_the_same_hull(self):
        self._put(
            {
                "character_id": 1001,
                "fitting_id": self.damnation.id,
                "bursts": ["armor", "armor", "armor"],
            }
        )
        self._in_fleet(1001, "Pilot One", DAMNATION_ID, timedelta(0))

        body = self._roles()
        armor = next(r for r in body["links"] if r["kind"] == "armor")[
            "pilots"
        ]
        self.assertEqual([("Pilot One", 3)], self._links(body)["armor"])
        self.assertTrue(armor[0]["in_fleet"])

    def test_hidden_roster_shows_only_your_own_pilots(self):
        self.fleet.hide_volunteers = True
        self.fleet.save()
        EveFleetShipVolunteer.objects.create(
            eve_fleet=self.fleet,
            character_id=9001,
            character_name="Someone Else",
            fitting=self.devoter,
        )
        self._put({"character_id": 1001, "fitting_id": self.guardian.id})

        body = self._roles()
        self.assertEqual([], body["cynos"])
        self.assertEqual(
            ["Pilot One"], [p["character_name"] for p in body["logi"]]
        )

    def test_logi_fc_is_the_only_role_sign_up(self):
        url = f"{BASE_URL}/{self.fleet.id}/role-volunteers"
        for role in ("cyno", "links", "scout"):
            response = self.client.post(
                url,
                {"character_id": 1001, "role": role},
                "application/json",
                **self.auth,
            )
            self.assertEqual(400, response.status_code, role)

        response = self.client.post(
            url,
            {"character_id": 1001, "role": "logi_anchor"},
            "application/json",
            **self.auth,
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(
            ["Pilot One"],
            [v["character_name"] for v in self._roles()["logi_fc"]],
        )

    def test_old_cyno_sign_ups_no_longer_show(self):
        EveFleetRoleVolunteer.objects.create(
            eve_fleet=self.fleet,
            character_id=1001,
            character_name="Pilot One",
            role=EveFleetRoleVolunteer.ROLE_CYNO,
        )

        response = self.client.get(
            f"{BASE_URL}/{self.fleet.id}/role-volunteers", **self.auth
        )
        self.assertEqual([], response.json())
        self.assertEqual([], self._roles()["cynos"])
        cynos = dict(_motd_role_volunteers(self.fleet))["Cynos"]
        self.assertEqual([], cynos)

    def test_composition_reports_fit_roles(self):
        response = self.client.get(
            f"{BASE_URL}/{self.fleet.id}/composition", **self.auth
        )
        by_name = {row["name"]: row["fit_roles"] for row in response.json()}
        damnation = by_name["[FL33T] 3X/4X Damnation"]
        self.assertEqual(3, damnation["burst_slots"])
        self.assertEqual(
            {"armor": 3, "skirmish": 2, "information": 2},
            damnation["bursts_fitted"],
        )
        self.assertTrue(by_name["Devoter"]["cyno"])

    def test_forbidden_without_fleet_access(self):
        other = User.objects.create(username="other")
        response = self.client.get(
            f"{BASE_URL}/{self.fleet.id}/roles",
            HTTP_AUTHORIZATION=f"Bearer {token_for(other)}",
        )
        self.assertEqual(403, response.status_code)
