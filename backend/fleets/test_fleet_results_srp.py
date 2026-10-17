from datetime import timedelta

from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone
from eveuniverse.models import EveCategory, EveGroup, EveType

from app.test import TestCase
from eveonline.models import EveCharacter
from feed.models import FeedEvent, FeedEventFleetLink
from fleets.models import EveFleetInstance
from fleets.tests import (
    BASE_URL,
    disconnect_fleet_signals,
    make_test_fleet,
    setup_fleet_reference_data,
)
from srp.models import (
    EveFleetShipReimbursement,
    ShipReimbursementProgram,
    ShipReimbursementProgramAmount,
)

PILOT = 2001
ALT = 2002
ENEMY = 3001
REVELATION = 19720
TYPHOON = 644
CAPSULE = 670


def row(killmail_id, outcome, victim, ship, value, capsule=False):
    return {
        "killmail_id": killmail_id,
        "killmail_time": timezone.now().isoformat(),
        "outcome": outcome,
        "solar_system_id": 30002097,
        "solar_system_name": "Dal",
        "victim_ship_type_id": ship,
        "victim_ship_name": {REVELATION: "Revelation", TYPHOON: "Typhoon"}.get(
            ship, "Capsule"
        ),
        "victim_character_id": victim,
        "victim_character_name": f"Pilot {victim}",
        "isk_value": value,
        "fleet_pilots": 3,
        "is_capsule": capsule,
    }


class FleetResultsSrpTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        disconnect_fleet_signals()
        setup_fleet_reference_data()
        self.fleet = make_test_fleet("Fortizar timer", self.user)
        self.instance = EveFleetInstance.objects.create(
            id=1260612315062, eve_fleet=self.fleet
        )
        EveFleetInstance.objects.filter(pk=self.instance.pk).update(
            end_time=timezone.now() - timedelta(hours=1)
        )

    def store(self, rows, instance=None):
        event = FeedEvent.objects.create(
            kind=FeedEvent.Kind.FLEET_KILLS,
            occurred_at=timezone.now(),
            title="Fleet kills",
            payload={"killmails": rows},
            rollup_code="fleet_kills",
        )
        FeedEventFleetLink.objects.create(
            feed_event=event,
            fleet_instance_id=(instance or self.instance).id,
        )

    def get(self, path):
        return self.client.get(
            f"{BASE_URL}{path}", HTTP_AUTHORIZATION=f"Bearer {self.token}"
        )

    def test_results_sum_stored_cards_per_fleet(self):
        self.store(
            [
                row(1, "kill", ENEMY, TYPHOON, 300),
                row(2, "kill", ENEMY, CAPSULE, 20, capsule=True),
                row(3, "loss", PILOT, TYPHOON, 250),
            ]
        )
        response = self.get(f"/results?fleet_ids={self.fleet.id},999999")

        self.assertEqual(200, response.status_code)
        self.assertEqual(
            [
                {
                    "fleet_id": self.fleet.id,
                    "isk_destroyed": 320,
                    "isk_lost": 250,
                    "ships_destroyed": 1,
                    "pods_destroyed": 1,
                    "ships_lost": 1,
                    "pods_lost": 0,
                }
            ],
            response.json(),
        )

    def test_results_leave_out_fleets_without_a_card(self):
        response = self.get(f"/results?fleet_ids={self.fleet.id}")
        self.assertEqual([], response.json())

    def test_results_skip_fleets_the_caller_cannot_see(self):
        other = make_test_fleet(
            "Other fleet", User.objects.create(username="o")
        )
        other_instance = EveFleetInstance.objects.create(
            id=1260612315063, eve_fleet=other
        )
        other.audience = None
        other.save()
        self.store([row(9, "kill", ENEMY, TYPHOON, 5)], other_instance)

        response = self.get(f"/results?fleet_ids={other.id}")
        self.assertEqual(200, response.status_code)
        self.assertEqual([], response.json())

    def make_program(self, type_id, name, amount):
        category, _ = EveCategory.objects.get_or_create(
            id=6, defaults={"name": "Ship", "published": True}
        )
        group, _ = EveGroup.objects.get_or_create(
            id=485,
            defaults={
                "name": "Dreadnought",
                "eve_category": category,
                "published": True,
            },
        )
        eve_type = EveType.objects.create(
            id=type_id, name=name, eve_group=group, published=True
        )
        program = ShipReimbursementProgram.objects.create(eve_type=eve_type)
        ShipReimbursementProgramAmount.objects.create(
            program=program, srp_value=amount
        )

    def test_my_srp_lists_only_covered_ship_losses_of_my_characters(self):
        EveCharacter.objects.create(
            character_id=PILOT, character_name="Pilot", user=self.user
        )
        EveCharacter.objects.create(
            character_id=ALT, character_name="Alt", user=self.user
        )
        self.make_program(REVELATION, "Revelation", 2_000_000_000)
        self.store(
            [
                row(1, "loss", PILOT, REVELATION, 2_100_000_000),
                row(2, "loss", ALT, TYPHOON, 250_000_000),  # not covered
                row(3, "loss", ALT, CAPSULE, 10, capsule=True),
                row(4, "loss", ENEMY, REVELATION, 1),  # not my character
                row(5, "kill", ENEMY, REVELATION, 1),
            ]
        )

        response = self.get(f"/{self.fleet.id}/my-srp")

        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertEqual([1], [loss["killmail_id"] for loss in body])
        self.assertEqual(2_000_000_000, body[0]["amount"])
        self.assertEqual("Revelation", body[0]["ship_name"])
        self.assertFalse(body[0]["filed"])

    def test_my_srp_marks_filed_claims(self):
        EveCharacter.objects.create(
            character_id=PILOT, character_name="Pilot", user=self.user
        )
        self.make_program(REVELATION, "Revelation", 2_000_000_000)
        self.store([row(1, "loss", PILOT, REVELATION, 2_100_000_000)])
        EveFleetShipReimbursement.objects.create(
            fleet=self.fleet,
            external_killmail_link="https://zkillboard.com/kill/1/",
            killmail_id=1,
            character_id=PILOT,
            character_name="Pilot",
            primary_character_id=PILOT,
            primary_character_name="Pilot",
            amount=2_000_000_000,
            ship_name="Revelation",
            ship_type_id=REVELATION,
            user=self.user,
        )

        body = self.get(f"/{self.fleet.id}/my-srp").json()

        self.assertTrue(body[0]["filed"])

    def test_my_srp_not_found(self):
        self.assertEqual(404, self.get("/999999/my-srp").status_code)
