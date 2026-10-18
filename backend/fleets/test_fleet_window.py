"""The desktop fleet window: FC summary, member view, roster privacy, caching."""

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client
from django.utils import timezone

from app.test import TestCase
from app.testing import make_token
from eveonline.helpers.characters import set_primary_character
from eveonline.models import EveCharacter
from fittings.models import EveDoctrine, EveDoctrineFitting, EveFitting
from fleets.helpers import fleet_window
from fleets.models import (
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
from fleets.tests import (
    BASE_URL,
    disconnect_fleet_signals,
    make_test_fleet,
    setup_fleet_reference_data,
)
from srp.models import EveFleetShipReimbursement
from users.helpers import add_user_permission

RIFTER_ID = 587
CAPSULE_ID = 670
AMAMAKE, HEK = 30002537, 30002053
FC_CHARACTER = 5000


def no_kills(fleet):
    return {
        "fleet_id": fleet.id,
        "tracked": True,
        "killmails": [],
        "isk_destroyed": 0,
        "isk_lost": 0,
        "ships_destroyed": 0,
        "pods_destroyed": 0,
        "ships_lost": 0,
        "pods_lost": 0,
    }


def loss_row(killmail_id, character_id, minutes_ago=2, outcome="loss"):
    return {
        "killmail_id": killmail_id,
        "killmail_time": (
            timezone.now() - timedelta(minutes=minutes_ago)
        ).isoformat(),
        "outcome": outcome,
        "solar_system_id": AMAMAKE,
        "solar_system_name": "Amamake",
        "victim_ship_type_id": GUARDIAN_ID,
        "victim_ship_name": "Guardian",
        "victim_character_id": character_id,
        "victim_character_name": f"Pilot {character_id}",
        "isk_value": 250_000_000,
        "fleet_pilots": 4,
        "is_capsule": False,
    }


@patch("fleets.helpers.fleet_window.fleet_kill_report", no_kills)
class FleetWindowTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()
        disconnect_fleet_signals()
        setup_fleet_reference_data()
        super().setUp()
        add_user_permission(self.user, "view_evefleet")
        self.auth = {"HTTP_AUTHORIZATION": f"Bearer {self.token}"}
        EveCharacter.objects.create(
            character_id=1001, character_name="Pilot One", user=self.user
        )

        self.fc_user = User.objects.create(username="fc")
        add_user_permission(self.fc_user, "view_evefleet")
        set_primary_character(
            self.fc_user,
            EveCharacter.objects.create(
                character_id=FC_CHARACTER,
                character_name="The FC",
                user=self.fc_user,
            ),
        )
        self.fc_auth = {
            "HTTP_AUTHORIZATION": f"Bearer {make_token(self.fc_user)}"
        }

        self.doctrine = EveDoctrine.objects.create(
            name="Armor Damnations", type="non_strategic", description=""
        )
        self.damnation = self._fit("Damnation", DAMNATION_ID, DAMNATION_EFT)
        self.guardian = self._fit("Guardian", GUARDIAN_ID, GUARDIAN_EFT)
        self.devoter = self._fit("Devoter", DEVOTER_ID, DEVOTER_EFT)
        self.fleet = make_test_fleet("Roam", self.fc_user)
        self.fleet.doctrine = self.doctrine
        self.fleet.save()

    def _fit(self, name, ship_id, eft):
        fitting = EveFitting.objects.create(
            name=name, ship_id=ship_id, description="", eft_format=eft
        )
        EveDoctrineFitting.objects.create(
            doctrine=self.doctrine, fitting=fitting, role="primary"
        )
        return fitting

    def _start(self, **fields):
        self.instance = EveFleetInstance.objects.create(
            id=900,
            eve_fleet=self.fleet,
            boss_id=FC_CHARACTER,
            last_updated=timezone.now(),
            **fields,
        )

    def _member(
        self, character_id, ship_id, system=AMAMAKE, docked=False, left=False
    ):
        member = EveFleetInstanceMember.objects.create(
            eve_fleet_instance=self.instance,
            character_id=character_id,
            character_name=f"Pilot {character_id}",
            ship_type_id=ship_id,
            ship_name=f"Ship {ship_id}",
            solar_system_id=system,
            solar_system_name="Amamake" if system == AMAMAKE else "Hek",
            station_id=60000001 if docked else None,
            squad_id=1,
            wing_id=1,
            join_time=timezone.now(),
        )
        if left:
            EveFleetInstanceMember.objects.filter(pk=member.pk).update(
                updated_at=timezone.now() - timedelta(hours=1)
            )

    def _volunteer(self, character_id, fitting):
        EveFleetShipVolunteer.objects.create(
            eve_fleet=self.fleet,
            character_id=character_id,
            character_name=f"Pilot {character_id}",
            fitting=fitting,
        )

    def _live_fleet(self):
        self._start()
        self._member(FC_CHARACTER, DAMNATION_ID)
        self._member(1001, GUARDIAN_ID)
        self._member(3001, RIFTER_ID)
        self._member(3002, CAPSULE_ID)
        self._member(3003, DAMNATION_ID, system=HEK)
        self._member(3004, DAMNATION_ID, docked=True)
        self._member(3005, DAMNATION_ID, left=True)
        self._volunteer(1001, self.guardian)
        self._volunteer(3006, self.guardian)

    def _window(self, auth=None, **headers):
        response = self.client.get(
            f"{BASE_URL}/{self.fleet.id}/window",
            **(auth or self.auth),
            **headers,
        )
        self.assertEqual(200, response.status_code, response.content)
        return response.json()

    def _current(self, auth=None):
        response = self.client.get(
            f"{BASE_URL}/window/current", **(auth or self.auth)
        )
        self.assertEqual(200, response.status_code, response.content)
        return response.json()["window"]

    def test_fc_gets_the_summary_and_the_roster(self):
        self._live_fleet()

        body = self._window(self.fc_auth)

        self.assertEqual("fc", body["mode"])
        self.assertTrue(body["fleet"]["live"])
        self.assertEqual("Armor Damnations", body["fleet"]["title"])
        self.assertEqual("The FC", body["fleet"]["fc_name"])
        self.assertEqual("Amamake", body["fleet"]["fc_system_name"])
        # 3005 left an hour ago.
        self.assertEqual(6, body["counts"]["in_fleet"])
        self.assertEqual(5, body["counts"]["with_fc"])
        ships = {
            s["ship_name"]: (s["flying"], s["signed_up"])
            for s in body["ships"]
        }
        self.assertEqual(
            {"Damnation": (3, 0), "Guardian": (1, 2), "Devoter": (0, 0)},
            ships,
        )
        self.assertEqual(
            {"Damnation": "Links", "Guardian": "Logi", "Devoter": "Cyno"},
            {s["ship_name"]: s["role_label"] for s in body["ships"]},
        )
        self.assertEqual(
            {"logi": True, "links": True, "cyno": False},
            {r["role"]: r["covered"] for r in body["roles"]},
        )
        self.assertEqual(
            [("ship", 1, "Guardian"), ("role", 1, "cyno")],
            [(n["kind"], n["count"], n["label"]) for n in body["needs"]],
        )
        self.assertEqual(6, len(body["pilots"]))
        self.assertEqual(
            {
                "capsule": ["Pilot 3002"],
                "off_doctrine": ["Pilot 3001"],
                "docked": ["Pilot 3004"],
                "away": ["Pilot 3003"],
                # Signed up for a Guardian, never joined.
                "not_in_fleet": ["Pilot 3006"],
            },
            {a["reason"]: a["names"] for a in body["attention"]},
        )

    def test_a_member_sees_their_ship_but_never_the_roster(self):
        self._live_fleet()

        body = self._window()

        self.assertEqual("member", body["mode"])
        self.assertEqual([], body["pilots"])
        self.assertEqual([], body["attention"])
        self.assertEqual(6, body["counts"]["in_fleet"])
        (me,) = body["me"]["characters"]
        self.assertEqual(1001, me["character_id"])
        self.assertTrue(me["doctrine"])
        self.assertEqual(
            {"1001": f"f:{self.guardian.id}"}, body["me"]["ship_volunteers"]
        )

    def test_only_managers_read_the_member_list(self):
        self._live_fleet()
        url = f"{BASE_URL}/{self.fleet.id}/members"

        self.assertEqual(403, self.client.get(url, **self.auth).status_code)
        self.assertEqual(200, self.client.get(url, **self.fc_auth).status_code)

    def test_a_pending_fleet_counts_sign_ups(self):
        self._volunteer(1001, self.devoter)

        body = self._window()

        self.assertEqual("viewer", body["mode"])
        self.assertFalse(body["fleet"]["live"])
        self.assertEqual([], body["needs"])
        self.assertEqual(
            {"logi": False, "links": False, "cyno": True},
            {r["role"]: r["covered"] for r in body["roles"]},
        )

    def test_current_finds_the_fleet_you_are_in(self):
        self.assertIsNone(self._current())

        self._live_fleet()
        cache.clear()

        self.assertEqual(self.fleet.id, self._current()["fleet"]["id"])
        self.assertEqual("fc", self._current(self.fc_auth)["mode"])

    def test_current_drops_a_pilot_who_left(self):
        self._start()
        self._member(1001, GUARDIAN_ID, left=True)

        self.assertIsNone(self._current())

    def test_fc_keeps_the_after_action_once_the_fleet_closes(self):
        self._live_fleet()
        EveFleetInstance.objects.filter(pk=self.instance.pk).update(
            start_time=timezone.now() - timedelta(hours=2),
            end_time=timezone.now() - timedelta(minutes=5),
        )
        cache.clear()

        self.assertIsNone(self._current())
        body = self._current(self.fc_auth)
        self.assertFalse(body["fleet"]["live"])
        self.assertEqual(7, body["after_action"]["pilots"])
        self.assertGreater(body["after_action"]["duration_seconds"], 6000)
        self.assertEqual([], body["pilots"])

    def test_a_recent_loss_shows_once_with_its_srp_state(self):
        self._live_fleet()
        report = no_kills(self.fleet)
        report["killmails"] = [
            {
                "killmail_id": 77,
                "killmail_time": (
                    timezone.now() - timedelta(minutes=2)
                ).isoformat(),
                "outcome": "loss",
                "solar_system_id": AMAMAKE,
                "solar_system_name": "Amamake",
                "victim_ship_type_id": GUARDIAN_ID,
                "victim_ship_name": "Guardian",
                "victim_character_id": 1001,
                "isk_value": 250_000_000,
                "is_capsule": False,
            }
        ]
        with patch(
            "fleets.helpers.fleet_window.fleet_kill_report",
            lambda fleet: report,
        ):
            body = self._window()

        loss = body["me"]["last_loss"]
        self.assertEqual(77, loss["killmail_id"])
        self.assertFalse(loss["srp_filed"])

    def test_unchanged_window_answers_304(self):
        self._live_fleet()
        response = self.client.get(
            f"{BASE_URL}/{self.fleet.id}/window", **self.auth
        )
        etag = response["ETag"]

        again = self.client.get(
            f"{BASE_URL}/{self.fleet.id}/window",
            HTTP_IF_NONE_MATCH=etag,
            **self.auth,
        )

        self.assertEqual(304, again.status_code)
        self.assertEqual(b"", again.content)

    def test_viewers_share_one_build_until_the_fleet_changes(self):
        self._live_fleet()
        with patch.object(
            fleet_window,
            "_build_shared",
            wraps=fleet_window._build_shared,  # pylint: disable=protected-access
        ) as build:
            self._window()
            self._window(self.fc_auth)
            self.assertEqual(1, build.call_count)

            # The poller stamps the instance: the next read rebuilds.
            EveFleetInstance.objects.filter(pk=self.instance.pk).update(
                last_updated=timezone.now() + timedelta(seconds=30)
            )
            self._window()
            self.assertEqual(2, build.call_count)

    def test_a_ship_sign_up_shows_at_once(self):
        self._live_fleet()
        self._window()

        response = self.client.put(
            f"{BASE_URL}/{self.fleet.id}/my-ship-volunteers",
            {
                "selections": [
                    {"character_id": 1001, "fitting_id": self.devoter.id}
                ]
            },
            "application/json",
            **self.auth,
        )
        self.assertEqual(200, response.status_code, response.content)

        ships = {
            s["ship_name"]: s["signed_up"] for s in self._window()["ships"]
        }
        self.assertEqual(1, ships["Devoter"])
        self.assertEqual(1, ships["Guardian"])

    def test_only_the_fc_gets_the_kill_feed(self):
        self._live_fleet()
        report = no_kills(self.fleet)
        report["killmails"] = [
            loss_row(78, 9999, minutes_ago=1, outcome="kill"),
            loss_row(77, 1001),
        ]
        report["ships_destroyed"], report["ships_lost"] = 1, 1
        with patch(
            "fleets.helpers.fleet_window.fleet_kill_report",
            lambda fleet: report,
        ):
            fc = self._window(self.fc_auth)
            member = self._window()

        self.assertEqual(
            [(78, "kill"), (77, "loss")],
            [(r["killmail_id"], r["outcome"]) for r in fc["feed"]],
        )
        self.assertEqual("Pilot 9999", fc["feed"][0]["victim_name"])
        self.assertEqual([], member["feed"])

    def test_a_pilot_flying_an_alt_is_not_missing(self):
        EveCharacter.objects.create(
            character_id=1002, character_name="Pilot Alt", user=self.user
        )
        self._start()
        self._member(FC_CHARACTER, DAMNATION_ID)
        self._member(1001, GUARDIAN_ID)
        self._volunteer(1002, self.guardian)

        body = self._window(self.fc_auth)

        self.assertNotIn(
            "not_in_fleet", [a["reason"] for a in body["attention"]]
        )

    def _mine(self, auth=None):
        response = self.client.get(
            f"{BASE_URL}/window/mine", **(auth or self.auth)
        )
        self.assertEqual(200, response.status_code, response.content)
        return response.json()

    def test_recent_lists_fleets_flown_with_srp_owed(self):
        self._live_fleet()
        EveFleetInstance.objects.filter(pk=self.instance.pk).update(
            end_time=timezone.now()
        )
        report = no_kills(self.fleet)
        report["killmails"] = [loss_row(77, 1001), loss_row(79, 1001)]
        report["ships_lost"] = 2
        EveFleetShipReimbursement.objects.create(
            fleet=self.fleet,
            external_killmail_link="https://zkillboard.com/kill/79/",
            status="approved",
            killmail_id=79,
            character_id=1001,
            character_name="Pilot One",
            primary_character_id=1001,
            primary_character_name="Pilot One",
            amount=42_000_000,
            ship_name="Guardian",
            ship_type_id=GUARDIAN_ID,
        )
        with patch(
            "fleets.helpers.my_fleets.fleet_kill_report",
            lambda fleet: report,
        ):
            body = self._mine()

        (row,) = body["fleets"]
        self.assertEqual(self.fleet.id, row["fleet_id"])
        self.assertEqual("Armor Damnations", row["title"])
        self.assertFalse(row["live"])
        self.assertFalse(row["was_fc"])
        self.assertEqual(
            {77: ("none", 0), 79: ("approved", 42_000_000)},
            {
                loss["killmail_id"]: (loss["srp_status"], loss["srp_amount"])
                for loss in row["my_losses"]
            },
        )
        self.assertEqual(1, body["srp_owed"])

    def test_recent_is_empty_for_someone_who_never_flew(self):
        body = self._mine()

        self.assertEqual([], body["fleets"])
        self.assertEqual(0, body["srp_owed"])

    def test_signups_name_the_fit_for_upcoming_fleets(self):
        self._volunteer(1001, self.guardian)
        self._volunteer(3006, self.guardian)

        (signup,) = self._mine()["signups"]

        self.assertEqual(self.fleet.id, signup["fleet_id"])
        self.assertEqual(1001, signup["character_id"])
        self.assertIn("Guardian", signup["fit_name"])
        self.assertEqual(GUARDIAN_ID, signup["ship_type_id"])
