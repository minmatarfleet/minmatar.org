"""Public kills of a finished fleet: anonymous, and nothing about our side."""

from datetime import timedelta

from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone

from app.test import TestCase
from eveonline.helpers.characters import set_primary_character
from eveonline.models import EveCharacter
from feed.models import FeedEvent, FeedEventFleetLink
from fleets.models import (
    EveFleetAudience,
    EveFleetFightTimeline,
    EveFleetInstance,
)
from fleets.models import EveFleetInstanceMember
from fleets.tests import (
    BASE_URL,
    disconnect_fleet_signals,
    make_test_fleet,
    setup_fleet_reference_data,
)
from tribes.models import Tribe, TribeGroup

OUR_PILOT = "Our Lost Pilot"
ROSTER_PILOT = "Our Secret Pilot"


def _row(killmail_id, minutes_ago, outcome, **fields):
    row = {
        "killmail_id": killmail_id,
        "killmail_time": (
            timezone.now() - timedelta(minutes=minutes_ago)
        ).isoformat(),
        "outcome": outcome,
        "solar_system_id": 30002537,
        "solar_system_name": "Amamake",
        "victim_ship_type_id": 587,
        "victim_ship_name": "Rifter",
        "victim_character_id": 9001,
        "victim_character_name": "Hostile Pilot",
        "isk_value": 1_000_000,
        "fleet_pilots": 12,
        "is_capsule": False,
    }
    row.update(fields)
    return row


class FleetPublicKillsTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        disconnect_fleet_signals()
        setup_fleet_reference_data()
        self.fc_user = User.objects.create(username="fc")
        fc = EveCharacter.objects.create(
            character_id=2001, character_name="The FC", user=self.fc_user
        )
        set_primary_character(self.fc_user, fc)
        self.fleet = make_test_fleet("Secret staging plan", self.fc_user)
        self.fleet.objective = "Hold Amamake"
        self.fleet.status = "complete"
        self.fleet.save()
        self.instance = EveFleetInstance.objects.create(
            id=8001, eve_fleet=self.fleet
        )
        self.started = timezone.now() - timedelta(hours=2)
        self.ended = timezone.now() - timedelta(minutes=5)
        EveFleetInstance.objects.filter(pk=self.instance.pk).update(
            start_time=self.started, end_time=self.ended
        )
        EveFleetInstanceMember.objects.create(
            eve_fleet_instance=self.instance,
            character_id=3002,
            character_name=ROSTER_PILOT,
            role="squad_member",
            role_name="Squad Member",
            ship_type_id=22430,
            ship_name="Sabre",
            solar_system_id=30002537,
            solar_system_name="Amamake",
            squad_id=1,
            wing_id=1,
        )
        EveFleetInstanceMember.objects.create(
            eve_fleet_instance=self.instance,
            character_id=3001,
            character_name=OUR_PILOT,
            role="squad_member",
            role_name="Squad Member",
            ship_type_id=644,
            ship_name="Typhoon",
            solar_system_id=30002537,
            solar_system_name="Amamake",
            squad_id=1,
            wing_id=1,
        )
        rows = [
            _row(1, 60, "kill", isk_value=50_000_000),
            _row(
                2,
                50,
                "loss",
                victim_ship_type_id=644,
                victim_ship_name="Typhoon",
                victim_character_id=3001,
                victim_character_name=OUR_PILOT,
                isk_value=150_000_000,
                solar_system_id=30002538,
                solar_system_name="Vard",
            ),
            _row(
                3,
                40,
                "kill",
                victim_ship_type_id=670,
                victim_ship_name="Capsule",
                is_capsule=True,
                isk_value=10_000_000,
            ),
        ]
        event = FeedEvent.objects.create(
            kind=FeedEvent.Kind.FLEET_KILLS,
            occurred_at=self.ended,
            title="Fleet kills",
            payload={"killmails": rows},
            rollup_code="fleet_kills",
            cluster_key=f"fleet_kills:{self.instance.id}",
        )
        FeedEventFleetLink.objects.create(
            feed_event=event, fleet_instance_id=self.instance.id
        )

    def _get(self, fleet_id=None, **headers):
        return self.client.get(
            f"{BASE_URL}/{fleet_id or self.fleet.id}/public-kills", **headers
        )

    def test_anonymous_viewer_gets_an_ended_fleet(self):
        response = self._get()

        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(self.fleet.id, body["fleet_id"])
        self.assertEqual("Hold Amamake", body["title"])
        self.assertEqual("training", body["fleet_type"])
        self.assertEqual(2001, body["fc_character_id"])
        self.assertEqual("The FC", body["fc_name"])
        self.assertEqual(["Amamake", "Vard"], body["systems"])
        self.assertEqual(1, body["ships_destroyed"])
        self.assertEqual(1, body["ships_lost"])
        self.assertEqual(60_000_000, body["isk_destroyed"])
        self.assertEqual(150_000_000, body["isk_lost"])
        self.assertEqual(29, body["efficiency"])
        self.assertEqual(
            [3, 2, 1], [k["killmail_id"] for k in body["killmails"]]
        )
        kill = body["killmails"][2]
        self.assertEqual("kill", kill["outcome"])
        self.assertEqual("Hostile Pilot", kill["victim_name"])
        self.assertEqual(9001, kill["victim_character_id"])
        self.assertIsNone(kill["victim_corporation_id"])
        self.assertTrue(body["killmails"][0]["is_capsule"])

    def test_nothing_about_our_pilots_leaks(self):
        response = self._get()
        body = response.json()

        # A pilot who flew and didn't die is nowhere on the public mails.
        self.assertNotIn(ROSTER_PILOT, response.content.decode())
        self.assertNotIn("Sabre", response.content.decode())
        self.assertNotIn("Secret staging plan", response.content.decode())
        # A loss is a public killmail: its victim shows like any other.
        loss = body["killmails"][1]
        self.assertEqual("loss", loss["outcome"])
        self.assertEqual("Typhoon", loss["victim_ship_name"])
        self.assertEqual(OUR_PILOT, loss["victim_name"])
        for key in (
            "description",
            "doctrine_id",
            "location",
            "members",
            "pilots",
            "tracking",
        ):
            self.assertNotIn(key, body)
        for killmail in body["killmails"]:
            self.assertNotIn("fleet_pilots", killmail)

    def test_numbers_count_our_fleet_against_hostiles_on_the_mails(self):
        EveFleetFightTimeline.objects.create(
            eve_fleet=self.fleet,
            killmails=[
                # Our kill: its victim was a hostile.
                {"outcome": "kill", "victim": 9001, "hostiles": []},
                # Their pod again: still one pilot.
                {"outcome": "kill", "victim": 9001, "hostiles": []},
                # Our loss: its attackers were hostiles, one of them twice.
                {
                    "outcome": "loss",
                    "victim": 3001,
                    "hostiles": [[99, 9002], [99, 9003], [98, 9001]],
                },
            ],
        )

        body = self._get().json()

        self.assertEqual(2, body["our_pilots"])
        self.assertEqual(3, body["hostile_pilots"])

    def test_numbers_wait_for_the_fight_timeline(self):
        body = self._get().json()

        self.assertEqual(2, body["our_pilots"])
        self.assertIsNone(body["hostile_pilots"])

    def test_signed_in_viewer_also_works(self):
        response = self._get(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        self.assertEqual(200, response.status_code)

    def test_live_fleet_is_not_found(self):
        later = EveFleetInstance.objects.create(id=8002, eve_fleet=self.fleet)
        self.assertIsNone(later.end_time)

        self.assertEqual(404, self._get().status_code)

    def test_untracked_or_unknown_fleet_is_not_found(self):
        untracked = make_test_fleet("Untracked", self.fc_user)

        self.assertEqual(404, self._get(untracked.id).status_code)
        self.assertEqual(404, self._get(999999).status_code)

    def test_cancelled_fleet_is_not_found(self):
        self.fleet.status = "cancelled"
        self.fleet.save()

        self.assertEqual(404, self._get().status_code)

    def test_members_only_group_fleet_is_not_found(self):
        tribe = Tribe.objects.create(name="Capitals", slug="capitals")
        self.fleet.host_group = TribeGroup.objects.create(
            tribe=tribe, name="Dreads"
        )
        self.fleet.audience = None
        self.fleet.save()

        self.assertEqual(404, self._get().status_code)

        self.fleet.open_to_alliance = True
        self.fleet.save()
        self.assertEqual(200, self._get().status_code)

    def test_hidden_audience_fleet_is_not_found(self):
        self.fleet.audience = EveFleetAudience.objects.create(
            name="Black ops", hidden=True
        )
        self.fleet.save()

        self.assertEqual(404, self._get().status_code)
