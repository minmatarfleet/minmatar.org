"""Finished-fleet Participants tab: hulls flown, reships, roles, no-shows."""

from datetime import timedelta

from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone
from eveuniverse.models import EveCategory, EveGroup, EveType

from app.test import TestCase
from app.testing import make_token
from eveonline.models import EveCharacter
from fittings.models import EveDoctrine, EveDoctrineFitting, EveFitting
from fleets.models import (
    EveFleetInstance,
    EveFleetInstanceMember,
    EveFleetInstanceMemberShipSnapshot,
    EveFleetRoleVolunteer,
    EveFleetShipVolunteer,
)
from fleets.test_fleet_roles import DAMNATION_EFT, DEVOTER_EFT, GUARDIAN_EFT
from fleets.tests import (
    BASE_URL,
    disconnect_fleet_signals,
    make_test_fleet,
    setup_fleet_reference_data,
)
from users.helpers import add_user_permission

CAPSULE = (670, "Capsule")
TYPHOON = (644, "Typhoon")
GUARDIAN = (11987, "Guardian")
DAMNATION = (22474, "Damnation")
DEVOTER = (12017, "Devoter")
ZARMAZD = (49712, "Zarmazd")
EXEQUROR = (634, "Exequror")

HULL_GROUPS = {
    CAPSULE: (29, "Capsule"),
    TYPHOON: (27, "Battleship"),
    GUARDIAN: (832, "Logistics"),
    ZARMAZD: (832, "Logistics"),
    DAMNATION: (540, "Command Ship"),
    DEVOTER: (894, "Heavy Interdiction Cruiser"),
    EXEQUROR: (26, "Cruiser"),
}

OWN = 1001  # the regular viewer's character


def _seed_hulls():
    category, _ = EveCategory.objects.get_or_create(
        id=6, defaults={"name": "Ship", "published": True}
    )
    for (type_id, name), (group_id, group_name) in HULL_GROUPS.items():
        group, _ = EveGroup.objects.get_or_create(
            id=group_id,
            defaults={
                "name": group_name,
                "published": True,
                "eve_category": category,
            },
        )
        EveType.objects.get_or_create(
            id=type_id,
            defaults={"name": name, "published": True, "eve_group": group},
        )


class FleetParticipantsTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        disconnect_fleet_signals()
        setup_fleet_reference_data()
        _seed_hulls()
        add_user_permission(self.user, "view_evefleet")
        EveCharacter.objects.create(
            character_id=OWN, character_name="Own Pilot", user=self.user
        )
        self.doctrine = EveDoctrine.objects.create(
            name="Armor", type="non_strategic", description=""
        )
        self.fits = {
            hull: self._doctrine_fit(name, hull[0], eft)
            for hull, name, eft in (
                (DAMNATION, "[FL33T] Damnation", DAMNATION_EFT),
                (GUARDIAN, "[FL33T] Guardian", GUARDIAN_EFT),
                (DEVOTER, "Devoter", DEVOTER_EFT),
            )
        }
        self.fc_user = User.objects.create(username="fc")
        self.fleet = make_test_fleet("Fleet", self.fc_user)
        self.fleet.doctrine = self.doctrine
        self.fleet.save()
        self.instance = EveFleetInstance.objects.create(
            id=7001, eve_fleet=self.fleet
        )
        EveFleetInstance.objects.filter(pk=self.instance.pk).update(
            end_time=timezone.now()
        )
        self.clock = timezone.now() - timedelta(hours=2)

        # Typhoon, podded, back in a Guardian: logi from a later hull.
        self._pilot(OWN, "Own Pilot", [TYPHOON, CAPSULE, GUARDIAN], GUARDIAN)
        # Typhoon, podded and stayed in the pod.
        self._pilot(3002, "Podded", [TYPHOON, CAPSULE], CAPSULE)
        # Joined in a pod, then boarded the links ship.
        self._pilot(3003, "Booster", [CAPSULE, DAMNATION], DAMNATION)
        # No snapshots at all: the member row is the only ship.
        self._pilot(3004, "Cyno Alt", [], DEVOTER)
        # Only ever a capsule.
        self._pilot(3005, "Pod Only", [CAPSULE], CAPSULE)
        # Off-doctrine logi hull: logi from its group.
        self._pilot(3006, "Trig", [ZARMAZD], ZARMAZD)
        # Off-doctrine cruiser: not logi without a fit.
        self._pilot(3007, "Exeq", [EXEQUROR], EXEQUROR)

    def _doctrine_fit(self, name, ship_id, eft):
        fitting = EveFitting.objects.create(
            name=name, ship_id=ship_id, description="", eft_format=eft
        )
        EveDoctrineFitting.objects.create(
            doctrine=self.doctrine, fitting=fitting, role="support"
        )
        return fitting

    def _pilot(self, character_id, name, snapshots, final, instance=None):
        member = EveFleetInstanceMember.objects.create(
            eve_fleet_instance=instance or self.instance,
            character_id=character_id,
            character_name=name,
            role="squad_member",
            role_name="Squad Member",
            ship_type_id=final[0],
            ship_name=final[1],
            solar_system_id=30002537,
            solar_system_name="Amamake",
            squad_id=1,
            wing_id=1,
        )
        for ship_type_id, ship_name in snapshots:
            snapshot = EveFleetInstanceMemberShipSnapshot.objects.create(
                member=member,
                ship_type_id=ship_type_id,
                ship_name=ship_name,
                solar_system_id=30002537,
                solar_system_name="Amamake",
            )
            self.clock += timedelta(minutes=1)
            EveFleetInstanceMemberShipSnapshot.objects.filter(
                pk=snapshot.pk
            ).update(created_at=self.clock)
        return member

    def _get(self, user=None, path="participants"):
        token = make_token(user) if user else self.token
        return self.client.get(
            f"{BASE_URL}/{self.fleet.id}/{path}",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

    def _body(self, user=None):
        response = self._get(user)
        self.assertEqual(200, response.status_code, response.content)
        return response.json()

    @staticmethod
    def _role(body, role):
        return next(row for row in body["roles_flown"] if row["role"] == role)

    def test_each_pilot_counts_once_by_first_non_capsule_ship(self):
        body = self._body()

        self.assertEqual(7, body["pilots"])
        self.assertEqual(
            [
                ("Typhoon", 2),
                ("Capsule", 1),
                ("Damnation", 1),
                ("Devoter", 1),
                ("Exequror", 1),
                ("Zarmazd", 1),
            ],
            [(row["ship_name"], row["count"]) for row in body["flew"]],
        )
        self.assertEqual(644, body["flew"][0]["ship_type_id"])

    def test_changed_ship_and_ended_in_pod(self):
        body = self._body()

        # Own Pilot (3 hulls), Podded and Booster (2 each).
        self.assertEqual(3, body["changed_ship"])
        # Podded and Pod Only.
        self.assertEqual(2, body["ended_in_pod"])

    def test_a_pilot_in_two_instances_is_one_pilot(self):
        later = EveFleetInstance.objects.create(id=7002, eve_fleet=self.fleet)
        EveFleetInstance.objects.filter(pk=later.pk).update(
            start_time=timezone.now() + timedelta(hours=1)
        )
        # Podded reships into a Typhoon in the second instance.
        self._pilot(3002, "Podded", [TYPHOON], TYPHOON, instance=later)

        body = self._body()
        self.assertEqual(7, body["pilots"])
        self.assertEqual(
            ("Typhoon", 2),
            (
                body["flew"][0]["ship_name"],
                body["flew"][0]["count"],
            ),
        )
        self.assertEqual(1, body["ended_in_pod"])

    def test_roles_come_from_any_hull_flown(self):
        body = self._body()

        logi = self._role(body, "logi")
        self.assertEqual("Logistics", logi["label"])
        self.assertEqual(2, logi["count"])
        self.assertEqual(
            [("Own Pilot", "Guardian"), ("Trig", "Zarmazd")],
            [(p["character_name"], p["ship_name"]) for p in logi["pilots"]],
        )
        self.assertEqual(
            [
                {"ship_name": "Guardian", "count": 1},
                {"ship_name": "Zarmazd", "count": 1},
            ],
            logi["hulls"],
        )
        links = self._role(body, "links")
        self.assertEqual(
            [(3003, "Damnation")],
            [(p["character_id"], p["ship_name"]) for p in links["pilots"]],
        )
        self.assertEqual(
            [{"ship_name": "Damnation", "count": 1}], links["hulls"]
        )
        cyno = self._role(body, "cyno")
        self.assertEqual(
            ["Cyno Alt"], [p["character_name"] for p in cyno["pilots"]]
        )

    def test_hidden_roster_names_only_your_own_pilots(self):
        self.fleet.hide_volunteers = True
        self.fleet.save()

        logi = self._role(self._body(), "logi")
        self.assertEqual(2, logi["count"])
        self.assertEqual([OWN], [p["character_id"] for p in logi["pilots"]])

    def test_logi_fc_volunteers(self):
        EveFleetRoleVolunteer.objects.create(
            eve_fleet=self.fleet,
            character_id=3006,
            character_name="Trig",
            role=EveFleetRoleVolunteer.ROLE_LOGI_ANCHOR,
        )
        body = self._body()
        self.assertEqual(
            ["Trig"], [v["character_name"] for v in body["logi_fc"]]
        )

    def _sign_up(self, character_id, name, hull):
        EveFleetShipVolunteer.objects.create(
            eve_fleet=self.fleet,
            character_id=character_id,
            character_name=name,
            fitting=self.fits[hull],
        )

    def test_no_shows_for_the_fc(self):
        self._sign_up(OWN, "Own Pilot", GUARDIAN)
        self._sign_up(9001, "Never Came", DEVOTER)

        body = self._body(self.fc_user)
        self.assertEqual(
            [
                {
                    "character_id": 9001,
                    "character_name": "Never Came",
                    "ship_name": "Devoter",
                    "ship_type_id": 12017,
                }
            ],
            body["no_shows"],
        )
        self.assertEqual(2, body["signed_up"])
        self.assertEqual(6, body["joined_without_signing_up"])

    def test_no_shows_hidden_from_a_regular_pilot(self):
        self._sign_up(9001, "Never Came", DEVOTER)

        body = self._body()
        self.assertIsNone(body["no_shows"])
        self.assertIsNone(body["signed_up"])
        self.assertIsNone(body["joined_without_signing_up"])

    def test_viewer_who_cannot_see_the_fleet(self):
        outsider = User.objects.create(username="outsider")

        expected = self._get(outsider, "roles").status_code
        self.assertEqual(403, expected)
        self.assertEqual(expected, self._get(outsider).status_code)

    def test_unknown_fleet(self):
        response = self.client.get(
            f"{BASE_URL}/999999/participants",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(404, response.status_code)
