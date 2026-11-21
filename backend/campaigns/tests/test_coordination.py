"""Coordination Discord: admins link a campaign to a server and channels."""

import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from campaigns.services import coordination
from campaigns.tests.helpers import auth_headers, grant, make_campaign
from discord.models import DiscordGuild

BASE = "/api/campaigns"
OURS = 1
OTHER = 222


def _channels(server_id):
    return [
        {"id": 10, "name": "timers", "type": "text", "guild_id": server_id},
        {"id": 11, "name": "pings", "type": "text", "guild_id": server_id},
        {"id": 12, "name": "voice", "type": "voice", "guild_id": server_id},
    ]


@override_settings(DISCORD_GUILD_ID=OURS, DISCORD_CLIENT_ID="bot-client")
class CoordinationTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.campaign = make_campaign()
        self.url = f"{BASE}/{self.campaign.slug}/coordination"
        DiscordGuild.objects.update_or_create(
            guild_id=OURS,
            defaults={
                "name": "Home",
                "is_primary": True,
                "is_active": True,
                "bot_is_administrator": False,
            },
        )
        DiscordGuild.objects.create(
            guild_id=OTHER,
            name="Allied",
            bot_is_administrator=True,
            last_seen_at=timezone.now(),
        )
        DiscordGuild.objects.create(guild_id=333, name="Gone", is_active=False)
        self.admin = User.objects.create(
            username="admin", is_superuser=True, is_staff=True
        )
        self.director = User.objects.create(username="director")
        grant(self.director, "change_campaign", "view_campaign")
        patcher = patch("campaigns.services.coordination.DiscordClient")
        self.discord = patcher.start().return_value
        self.discord.get_guild_channels.side_effect = _channels
        self.addCleanup(patcher.stop)

    def _put(self, user, body):
        return self.client.put(
            self.url,
            data=json.dumps(body),
            content_type="application/json",
            **auth_headers(user),
        )

    def test_admin_sees_default_server_and_servers_with_admin_flag(self):
        response = self.client.get(self.url, **auth_headers(self.admin))
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["is_default"])
        self.assertEqual(body["guild_id"], str(OURS))
        servers = {row["id"]: row for row in body["servers"]}
        self.assertEqual(set(servers), {str(OURS), str(OTHER)})
        self.assertTrue(servers[str(OTHER)]["is_administrator"])
        self.assertFalse(servers[str(OURS)]["is_administrator"])
        self.assertEqual(
            [row["name"] for row in body["channels"]], ["pings", "timers"]
        )
        self.assertIn("/discord/bot/connect?purpose=ours", body["invite_url"])
        self.assertIn("purpose=link", body["link_url"])
        url = coordination.authorize_url("state")
        self.assertIn("client_id=bot-client", url)
        self.assertIn("permissions=8", url)
        self.assertIn("response_type=code", url)

    def test_listing_another_server_shows_its_channels(self):
        response = self.client.get(
            f"{self.url}?guild_id={OTHER}", **auth_headers(self.admin)
        )
        self.assertEqual(response.json()["guild_id"], str(OTHER))
        self.discord.get_guild_channels.assert_called_with(OTHER)

    def test_server_the_bot_is_not_in_is_ignored(self):
        response = self.client.get(
            f"{self.url}?guild_id=333", **auth_headers(self.admin)
        )
        self.assertEqual(response.json()["guild_id"], str(OURS))

    def test_campaign_manager_without_the_gate_is_refused(self):
        self.assertEqual(
            self.client.get(
                self.url, **auth_headers(self.director)
            ).status_code,
            403,
        )
        response = self._put(self.director, {"guild_id": str(OTHER)})
        self.assertEqual(response.status_code, 403)
        self.campaign.refresh_from_db()
        self.assertIsNone(self.campaign.coordination_guild_id)

    def test_anonymous_is_refused(self):
        self.assertIn(self.client.get(self.url).status_code, (401, 403))

    def test_gate_is_a_registered_feature(self):
        self.assertEqual(coordination.FEATURE, "campaigns.coordination")

    def test_admin_links_another_server_and_channels(self):
        response = self._put(
            self.admin,
            {
                "guild_id": str(OTHER),
                "timers_channel_id": "10",
                "fleets_channel_id": "11",
            },
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["is_default"])
        self.assertEqual(body["timers_channel_id"], "10")
        self.assertEqual(body["fleets_channel_id"], "11")
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.coordination_guild_id, OTHER)
        self.assertEqual(self.campaign.coordination_timers_channel_id, 10)
        self.assertEqual(self.campaign.coordination_fleets_channel_id, 11)

    def test_choosing_our_server_stores_no_guild(self):
        self._put(self.admin, {"guild_id": str(OTHER)})
        response = self._put(
            self.admin, {"guild_id": str(OURS), "timers_channel_id": "10"}
        )
        self.assertEqual(response.status_code, 200)
        self.campaign.refresh_from_db()
        self.assertIsNone(self.campaign.coordination_guild_id)
        self.assertTrue(response.json()["is_default"])

    def test_unknown_server_is_refused(self):
        for server in ("333", "999"):
            response = self._put(self.admin, {"guild_id": server})
            self.assertEqual(response.status_code, 400)
        self.campaign.refresh_from_db()
        self.assertIsNone(self.campaign.coordination_guild_id)

    def test_channel_outside_the_server_or_not_text_is_refused(self):
        for channel in ("99", "12"):
            response = self._put(
                self.admin,
                {"guild_id": str(OTHER), "timers_channel_id": channel},
            )
            self.assertEqual(response.status_code, 400)
        self.campaign.refresh_from_db()
        self.assertIsNone(self.campaign.coordination_timers_channel_id)

    def test_channels_unavailable_when_discord_fails(self):
        self.discord.get_guild_channels.side_effect = RuntimeError("down")
        body = self.client.get(self.url, **auth_headers(self.admin)).json()
        self.assertTrue(body["channels_unavailable"])
        self.assertEqual(body["channels"], [])
        response = self._put(
            self.admin, {"guild_id": str(OTHER), "timers_channel_id": "10"}
        )
        self.assertEqual(response.status_code, 400)

    def test_clearing_channels_skips_validation(self):
        self._put(
            self.admin, {"guild_id": str(OTHER), "timers_channel_id": "10"}
        )
        self.discord.get_guild_channels.side_effect = RuntimeError("down")
        response = self._put(self.admin, {"guild_id": str(OTHER)})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["timers_channel_id"])
        self.campaign.refresh_from_db()
        self.assertIsNone(self.campaign.coordination_timers_channel_id)

    def test_stored_channels_hidden_while_browsing_another_server(self):
        self._put(
            self.admin, {"guild_id": str(OTHER), "timers_channel_id": "10"}
        )
        body = self.client.get(
            f"{self.url}?guild_id={OURS}", **auth_headers(self.admin)
        ).json()
        self.assertIsNone(body["timers_channel_id"])

    @override_settings(DISCORD_CLIENT_ID="")
    def test_no_invite_without_a_client_id(self):
        body = self.client.get(self.url, **auth_headers(self.admin)).json()
        self.assertEqual(body["invite_url"], "")

    def test_settings_payload_never_shows_the_server(self):
        self._put(self.admin, {"guild_id": str(OTHER)})
        response = self.client.get(
            f"{BASE}/{self.campaign.slug}/settings",
            **auth_headers(self.director),
        )
        self.assertNotIn(str(OTHER), response.content.decode())
