"""Voice options on fleets: scheduling, the MOTD line, and the tasks."""

import json
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.core.cache import cache
from django.test import Client
from django.utils import timezone

from app.testing import make_token
from discord.models import DiscordChannel, DiscordGuild
from fleets.helpers.copy_fleet import _copy_request
from fleets.helpers.voice_channels import ping_voice
from fleets.models import EveFleet, EveFleetAudience, FleetVoiceOption
from fleets.notifications import get_fleet_discord_notification
from fleets.motd import get_motd
from fleets.tests import setup_fleet_reference_data
from voice import store
from voice.tasks import expire_grants, heartbeat_check, heartbeat_problem
from voice.models import VoiceChannelLease
from voice.tests.helpers import VoiceTestCase


class FleetFormCase(VoiceTestCase):
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


class VoiceOptionTest(FleetFormCase):
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

    def test_copying_a_fleet_whose_option_was_switched_off_uses_the_default(
        self,
    ):
        fleet = self.fleet(self.fc_user)
        self.mumble.is_active = False
        self.mumble.save()
        request = _copy_request(fleet, timezone.now() + timedelta(days=7), [])
        self.assertIsNone(request.voice_option_id)
        self.mumble.is_active = True
        self.mumble.save()
        request = _copy_request(fleet, timezone.now() + timedelta(days=7), [])
        self.assertEqual(request.voice_option_id, self.mumble.id)

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
        # A restricted fleet: Fleet 1 is for open fleets.
        self.assertEqual(leases["2"]["fleet_id"], fleet.id)

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


ALLIANCE_GUILD = 1  # settings_test.DISCORD_GUILD_ID
FW_GUILD = 712126510374584320


def _discord_channels(guild_id):
    """A server's channels as Discord sends them."""
    everyone_denied = [
        {"id": str(guild_id), "type": 0, "allow": "0", "deny": str(1 << 10)}
    ]
    return [
        {"id": "10", "type": 4, "name": "Voice", "position": 1},
        {
            "id": "11",
            "type": 4,
            "name": "Staff",
            "position": 0,
            "permission_overwrites": everyone_denied,
        },
        {
            "id": "101",
            "type": 2,
            "name": "Fleet 2",
            "parent_id": "10",
            "position": 2,
        },
        {
            "id": "100",
            "type": 2,
            "name": "Fleet 1",
            "parent_id": "10",
            "position": 1,
        },
        {
            "id": "102",
            "type": 2,
            "name": "AFK",
            "parent_id": "10",
            "position": 3,
        },
        {
            "id": "103",
            "type": 2,
            "name": "Leadership",
            "parent_id": "10",
            "position": 4,
            "permission_overwrites": everyone_denied,
        },
        {
            "id": "110",
            "type": 2,
            "name": "Officers",
            "parent_id": "11",
            "position": 0,
        },
        {
            "id": "120",
            "type": 0,
            "name": "chat",
            "parent_id": "10",
            "position": 0,
        },
    ]


class VoiceChannelTest(FleetFormCase):
    """Picking a Discord voice channel, and the ping and MOTD linking it."""

    def setUp(self):
        super().setUp()
        cache.clear()
        guild, _ = DiscordGuild.objects.get_or_create(
            guild_id=ALLIANCE_GUILD, defaults={"name": "MF"}
        )
        DiscordChannel.objects.create(
            channel_id=102,
            guild=guild,
            name="AFK",
            channel_type="voice",
            hide_from_fleets=True,
        )
        self.discord.discord_guild_id = ALLIANCE_GUILD
        self.discord.discord_channel_id = 101
        self.discord.save()
        self.fw = FleetVoiceOption.objects.create(
            name="Minmatar Faction Warfare Discord",
            kind="discord",
            discord_guild_id=FW_GUILD,
            order=1,
        )
        patcher = patch(
            "fleets.helpers.voice_channels.DiscordClient.get_guild_channels_raw",
            side_effect=_discord_channels,
        )
        self.discord_api = patcher.start()
        self.addCleanup(patcher.stop)

    def options(self):
        return {
            o["name"]: o
            for o in Client()
            .get(
                "/api/fleets/voice-options",
                HTTP_AUTHORIZATION=f"Bearer {make_token(self.fc_user)}",
            )
            .json()
        }

    def test_lists_channels_people_can_join_in_discord_order(self):
        options = self.options()
        alliance = options["Minmatar Fleet Discord"]
        self.assertEqual(
            [
                (c["id"], c["name"], c["category"])
                for c in alliance["channels"]
            ],
            [("100", "Fleet 1", "Voice"), ("101", "Fleet 2", "Voice")],
        )
        self.assertEqual(alliance["default_channel_id"], "101")
        # No default set: the first channel.
        fw = options["Minmatar Faction Warfare Discord"]
        self.assertEqual(fw["default_channel_id"], "100")
        self.assertEqual(options["Mumble"]["channels"], [])
        # Cached: one Discord call per server.
        self.options()
        self.assertEqual(self.discord_api.call_count, 2)

    def test_discord_down_lists_no_channels(self):
        self.discord_api.side_effect = RuntimeError("down")
        options = self.options()
        self.assertEqual(options["Minmatar Fleet Discord"]["channels"], [])
        self.assertIsNone(
            options["Minmatar Fleet Discord"]["default_channel_id"]
        )

    def test_scheduling_stores_the_channel(self):
        body = self.create(voice_channel_id="100").json()
        self.assertEqual(body["voice_channel_id"], "100")
        self.assertEqual(body["voice_channel_name"], "Fleet 1")
        fleet = EveFleet.objects.get(id=body["id"])
        self.assertEqual(fleet.voice_channel_name, "Fleet 1")
        for unknown in ("102", "110", "999", "x"):
            self.assertEqual(
                self.create(voice_channel_id=unknown).status_code, 400, unknown
            )

    def test_mumble_open_only_sticks_to_mumble(self):
        body = self.create(
            voice_option_id=self.mumble.id, mumble_open=True
        ).json()
        self.assertTrue(body["mumble_open"])
        self.assertIsNone(body["voice_channel_id"])
        body = self.create(mumble_open=True).json()
        self.assertFalse(body["mumble_open"])

    def test_changing_the_server_drops_the_old_channel(self):
        fleet_id = self.create(voice_channel_id="100").json()["id"]

        def patch_fleet(**body):
            return Client().patch(
                f"/api/fleets/{fleet_id}",
                data=json.dumps(body),
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {make_token(self.fc_user)}",
            )

        self.assertEqual(
            patch_fleet(description="same voice").status_code, 200
        )
        self.assertEqual(
            EveFleet.objects.get(id=fleet_id).voice_channel_id, 100
        )
        self.assertEqual(
            patch_fleet(voice_option_id=self.fw.id).status_code, 200
        )
        fleet = EveFleet.objects.get(id=fleet_id)
        self.assertEqual(fleet.voice_option_id, self.fw.id)
        self.assertIsNone(fleet.voice_channel_id)
        patch_fleet(voice_channel_id="101")
        self.assertEqual(
            EveFleet.objects.get(id=fleet_id).voice_channel_id, 101
        )

    def test_ping_and_motd_link_the_channel(self):
        fleet = self.fleet(
            self.fc_user,
            mumble=False,
            voice_channel_id=100,
            voice_channel_name="Fleet 1",
        )
        line, url = ping_voice(fleet)
        self.assertEqual(line, "<#100>")
        self.assertEqual(url, "https://discord.com/channels/1/100")
        self.assertEqual(
            fleet.motd_voice(), (url, "Fleet 1 · Minmatar Fleet Discord")
        )
        fleet.voice_option = self.fw
        line, url = ping_voice(fleet)
        self.assertEqual(
            line,
            f"[Fleet 1](https://discord.com/channels/{FW_GUILD}/100)"
            " on Minmatar Faction Warfare Discord",
        )
        payload = get_fleet_discord_notification(
            fleet_id=1,
            fleet_type="Roam",
            fleet_location="Amamake",
            fleet_audience="Alliance",
            fleet_commander_name="FC",
            fleet_commander_id=1,
            fleet_description="x",
            fleet_voice_channel=line,
            fleet_voice_channel_link=url,
        )
        self.assertIn(
            f"**VOICE CHANNEL**: {line}\n", payload["embeds"][0]["description"]
        )
        button = payload["components"][0]["components"][0]
        self.assertEqual(button["url"], url)
        self.assertFalse(button["disabled"])

    def test_mumble_ping_says_whether_fleet_1_is_open(self):
        fleet = self.fleet(self.fc_user, mumble_open=True)
        line, url = ping_voice(fleet)
        self.assertTrue(url.endswith("/voice"))
        self.assertIn("Fleet 1, open to all members", line)
        # Another open fleet held Fleet 1: the ping names the real branch.
        self.lease(fleet, branch=2)
        self.assertTrue(ping_voice(fleet)[0].endswith(": Fleet 2"))
        restricted = self.fleet(self.fc_user)
        self.assertIn("your fleet's branch", ping_voice(restricted)[0])
        # A Discord fleet without a channel keeps the server's invite.
        plain = self.fleet(self.fc_user, mumble=False)
        self.assertEqual(
            ping_voice(plain),
            ("Minmatar Fleet Discord", "https://discord.gg/minmatar"),
        )

    def test_ping_preview_shows_the_picked_channel(self):
        def preview(**voice):
            return Client().post(
                "/api/fleets/ping-preview",
                data=json.dumps(
                    {
                        "type": "non_strategic",
                        "audience_id": self.audience.id,
                        **voice,
                    }
                ),
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {make_token(self.fc_user)}",
            )

        response = preview(
            voice_option_id=self.discord.id, voice_channel_id="100"
        )
        self.assertEqual(response.status_code, 200, response.content)
        description = response.json()["payload"]["embeds"][0]["description"]
        self.assertIn("**VOICE CHANNEL**: <#100>", description)
        # An unknown channel previews without one rather than failing.
        response = preview(
            voice_option_id=self.discord.id, voice_channel_id="999"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "**VOICE CHANNEL**: Minmatar Fleet Discord",
            response.json()["payload"]["embeds"][0]["description"],
        )
