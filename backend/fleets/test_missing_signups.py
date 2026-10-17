from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client
from django.utils import timezone

from app.test import TestCase
from discord.models import DiscordUser
from eveonline.models import EveCharacter
from fittings.models import EveFitting
from fleets.helpers.missing_signups import send_missing_signup_nudges
from fleets.models import (
    EveFleetInstance,
    EveFleetInstanceMember,
    EveFleetShipVolunteer,
)
from fleets.tests import (
    BASE_URL,
    disconnect_fleet_signals,
    make_test_fleet,
    setup_fleet_reference_data,
)

IN_FLEET = 2001
MISSING = 2002
MISSING_ALT = 2003
STRANGER = 2004


class MissingSignupsTestCase(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.client = Client()
        disconnect_fleet_signals()
        setup_fleet_reference_data()
        self.fleet = make_test_fleet("Fortizar timer", self.user)
        self.fitting = EveFitting.objects.create(
            name="Scythe [FL33T]",
            ship_id=631,
            description="",
            eft_format="[Scythe, Scythe [FL33T]]\nDamage Control II\n",
        )
        for character_id in (IN_FLEET, MISSING, MISSING_ALT):
            EveFleetShipVolunteer.objects.create(
                eve_fleet=self.fleet,
                character_id=character_id,
                character_name=f"Pilot {character_id}",
                fitting=self.fitting,
            )

    def go_live(self):
        instance = EveFleetInstance.objects.create(
            id=1260612315062, eve_fleet=self.fleet
        )
        EveFleetInstanceMember.objects.create(
            eve_fleet_instance=instance,
            character_id=IN_FLEET,
            character_name=f"Pilot {IN_FLEET}",
            role="squad_member",
            role_name="Squad Member",
            ship_type_id=587,
            ship_name="Rifter",
            solar_system_id=30002097,
            solar_system_name="Amamake",
            squad_id=1,
            wing_id=1,
        )
        EveFleetInstance.objects.filter(pk=instance.pk).update(
            last_updated=timezone.now() + timedelta(seconds=1)
        )
        return instance

    def get(self):
        return self.client.get(
            f"{BASE_URL}/{self.fleet.id}/missing-signups",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

    def nudge(self):
        return self.client.post(
            f"{BASE_URL}/{self.fleet.id}/missing-signups/nudge",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

    def test_empty_until_tracked(self):
        response = self.get()
        self.assertEqual(200, response.status_code)
        self.assertEqual([], response.json()["pilots"])

    def test_lists_volunteers_not_in_fleet(self):
        self.go_live()
        body = self.get().json()
        self.assertEqual(
            [MISSING, MISSING_ALT],
            [pilot["character_id"] for pilot in body["pilots"]],
        )
        self.assertIsNone(body["last_nudge"])
        self.assertIsNone(body["next_nudge_at"])

    def test_only_fleet_managers(self):
        self.fleet.created_by = User.objects.create(username="other-fc")
        self.fleet.save()
        self.assertEqual(403, self.get().status_code)
        self.assertEqual(403, self.nudge().status_code)

    @patch(
        "fleets.endpoints.fleet.post_fleet_missing_signups_nudge.nudge_missing_signups"
    )
    def test_nudge_queues_once_per_cooldown(self, task):
        self.go_live()
        first = self.nudge()
        self.assertEqual(202, first.status_code)
        self.assertEqual(2, first.json()["pilots"])
        task.delay.assert_called_once_with(self.fleet.id)

        self.assertEqual(429, self.nudge().status_code)
        self.assertEqual(1, task.delay.call_count)
        self.assertIsNotNone(self.get().json()["next_nudge_at"])

    @patch(
        "fleets.endpoints.fleet.post_fleet_missing_signups_nudge.nudge_missing_signups"
    )
    def test_nudge_refused_when_not_live(self, task):
        self.assertEqual(400, self.nudge().status_code)
        task.delay.assert_not_called()

    @patch("fleets.helpers.missing_signups.DiscordClient")
    def test_one_dm_per_player_and_failures_counted(self, client_class):
        self.go_live()
        player = User.objects.create(username="multiboxer")
        for character_id in (MISSING, MISSING_ALT):
            EveCharacter.objects.create(
                character_id=character_id,
                character_name=f"Pilot {character_id}",
                user=player,
            )
        DiscordUser.objects.create(id=555, discord_tag="mb", user=player)
        EveFleetShipVolunteer.objects.create(
            eve_fleet=self.fleet,
            character_id=STRANGER,
            character_name="No account",
            fitting=self.fitting,
        )

        result = send_missing_signup_nudges(self.fleet)

        send_dm = client_class.return_value.send_dm
        send_dm.assert_called_once()
        self.assertEqual("555", send_dm.call_args.args[0])
        message = send_dm.call_args.kwargs["message"]
        self.assertIn(f"Pilot {MISSING}", message)
        self.assertIn(f"Pilot {MISSING_ALT}", message)
        self.assertEqual(1, result["players"])
        self.assertEqual(1, result["delivered"])
        self.assertEqual(1, result["failed"])
        self.assertEqual(result, self.get().json()["last_nudge"])

    def test_tracking_reports_motd_and_free_move(self):
        instance = self.go_live()
        response = self.client.get(
            f"{BASE_URL}/{self.fleet.id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        tracking = response.json()["tracking"]
        self.assertFalse(tracking["has_motd"])
        self.assertFalse(tracking["is_free_move"])

        EveFleetInstance.objects.filter(pk=instance.pk).update(
            motd="Welcome", is_free_move=True
        )
        tracking = self.client.get(
            f"{BASE_URL}/{self.fleet.id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        ).json()["tracking"]
        self.assertTrue(tracking["has_motd"])
        self.assertTrue(tracking["is_free_move"])
