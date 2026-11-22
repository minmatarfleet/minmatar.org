"""Voice options on fleets: scheduling, the MOTD line, and the tasks."""

import json
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.test import Client
from django.utils import timezone

from app.testing import make_token
from fleets.models import EveFleetAudience, FleetVoiceOption
from fleets.motd import get_motd
from fleets.tests import setup_fleet_reference_data
from voice import store
from voice.tasks import expire_grants, heartbeat_check, heartbeat_problem
from voice.models import VoiceChannelLease
from voice.tests.helpers import VoiceTestCase


class VoiceOptionTest(VoiceTestCase):
    def setUp(self):
        super().setUp()
        setup_fleet_reference_data()
        self.fc_user, _ = self.pilot("fc", "Alliance")
        for codename in ("view_evefleet", "add_evefleet"):
            self.fc_user.user_permissions.add(
                Permission.objects.get(codename=codename)
            )
        self.audience = EveFleetAudience.objects.get(name="Test Audience")

    def create(self, **extra):
        body = {
            "type": "strategic",
            "description": "Voice test",
            "start_time": (timezone.now() + timedelta(days=1)).isoformat(),
            "audience_id": self.audience.id,
            "location_id": 123,
            **extra,
        }
        with patch("fleets.helpers.schedule_fleet.send_discord_pre_ping"):
            return Client().post(
                "/api/fleets",
                data=json.dumps(body),
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {make_token(self.fc_user)}",
            )

    def test_the_seed_keeps_discord_default_and_mumble_off(self):
        discord = FleetVoiceOption.objects.get(kind="discord")
        self.assertTrue(discord.is_default)
        self.assertEqual(discord.link, "https://discord.gg/minmatar")
        # The migration creates Mumble inactive (the test fixture switches it on).
        self.mumble.is_active = False
        self.mumble.save()
        response = self.create(voice_option_id=self.mumble.id)
        self.assertEqual(response.status_code, 400)

    def test_new_fleets_get_the_default_and_can_pick_mumble(self):
        plain = self.create()
        self.assertEqual(plain.status_code, 200, plain.content)
        self.assertEqual(plain.json()["voice_option_id"], self.discord.id)
        self.assertFalse(plain.json()["uses_mumble"])
        mumble = self.create(voice_option_id=self.mumble.id).json()
        self.assertTrue(mumble["uses_mumble"])

    def test_voice_options_lists_active_ones(self):
        body = (
            Client()
            .get(
                "/api/fleets/voice-options",
                HTTP_AUTHORIZATION=f"Bearer {make_token(self.fc_user)}",
            )
            .json()
        )
        self.assertEqual(
            [(o["kind"], o["is_default"]) for o in body],
            [("discord", True), ("mumble", False)],
        )

    def test_existing_motd_voice_line_is_unchanged(self):
        fleet = self.fleet(self.fc_user, mumble=False)
        fleet.voice_option = None  # fleets the backfill missed
        self.assertEqual(
            fleet.motd_voice(),
            ("https://discord.gg/minmatar", "Minmatar Fleet Discord"),
        )

    def test_mumble_motd_links_the_voice_page(self):
        fleet = self.fleet(self.fc_user)
        link, name = fleet.motd_voice()
        self.assertTrue(link.endswith("/voice"))
        motd = get_motd(1, "FC", None, None, link, name, None, None)
        self.assertIn("Voice: ", motd)
        self.assertIn(f'href="{link}"', motd)
        self.assertIn("Mumble — ", motd)


class VoiceTaskTest(VoiceTestCase):
    def test_heartbeat_problems(self):
        now = timezone.now()
        self.assertEqual(heartbeat_problem(None), "no heartbeat")
        fresh = json.dumps({"at": now.isoformat(), "authenticator": True})
        self.assertIsNone(heartbeat_problem(fresh, now))
        stale = json.dumps(
            {
                "at": (now - timedelta(seconds=90)).isoformat(),
                "authenticator": True,
            }
        )
        self.assertIn("old", heartbeat_problem(stale, now))
        unregistered = json.dumps(
            {"at": now.isoformat(), "authenticator": False}
        )
        self.assertEqual(
            heartbeat_problem(unregistered, now),
            "authenticator not registered",
        )

    def test_heartbeat_check_is_quiet_before_go_live(self):
        self.mumble.is_active = False
        self.mumble.save()
        with patch("voice.tasks.sentry_sdk.capture_message") as capture:
            self.assertIsNone(heartbeat_check())
        capture.assert_not_called()

    def test_heartbeat_check_alerts_sentry(self):
        with patch("voice.tasks.sentry_sdk.capture_message") as capture:
            self.assertEqual(heartbeat_check(), "no heartbeat")
        capture.assert_called_once()

    def test_expire_grants_leases_tracked_fleets_and_publishes(self):
        fc_user, _ = self.pilot("fc", "Alliance")
        fleet = self.fleet(fc_user)
        self.track(fleet)
        expire_grants()
        self.assertTrue(
            VoiceChannelLease.active().filter(fleet=fleet).exists()
        )
        leases = json.loads(store.memory_store().get(store.LEASES_KEY))
        self.assertEqual(leases["1"]["fleet_id"], fleet.id)

    def test_fleet_poll_queues_voice_work_for_mumble_fleets_only(self):
        fc_user, _ = self.pilot("fc", "Alliance")
        mumble = self.track(self.fleet(fc_user))
        discord = self.track(self.fleet(fc_user, mumble=False))
        # pylint: disable=import-outside-toplevel
        from fleets.models import EveFleetInstance
        from fleets.tasks import update_fleet_instances

        with patch.object(
            EveFleetInstance, "update_is_registered_status"
        ), patch.object(EveFleetInstance, "update_fleet_members"), patch(
            "fleets.tasks.app.signature"
        ) as signature:
            update_fleet_instances()
        queued = [call.kwargs["args"] for call in signature.call_args_list]
        self.assertEqual(queued, [[mumble.id]])
        del discord
