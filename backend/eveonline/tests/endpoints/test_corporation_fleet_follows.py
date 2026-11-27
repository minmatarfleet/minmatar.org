"""A corporation asks to get a tribe group's fleet posts in its own
Discord (docs/tribes/group-fleet-roundup.md)."""

from unittest.mock import patch

from django.contrib.auth.models import User
from django.db.models import signals
from django.test import Client, override_settings

from app.test import TestCase
from app.testing import make_token
from discord.models import DiscordGuild
from eveonline.constants import (
    MINMATAR_FLEET_ASSOCIATES_ALLIANCE_ID,
)
from eveonline.helpers.corporations.discord_bot import authorize_url
from eveonline.helpers.corporations.fleet_follows import (
    EMBED_LINKS,
    MENTION_EVERYONE,
    SEND_MESSAGES,
    follow_warnings,
)
from eveonline.models import EveAlliance, EveCharacter, EveCorporation
from tribes.models import TribeGroupCorporationFollow
from tribes.tests.publishing_fixtures import make_tribe_group

BASE_URL = "/api/eveonline/corporations/corporations"
CLIENT = "eveonline.helpers.corporations.fleet_follows.DiscordClient"
GUILD_ID = 4100
BOT_ID = "555"
VIEW_CHANNEL = 1 << 10
ALL_NEEDED = VIEW_CHANNEL | SEND_MESSAGES | EMBED_LINKS | MENTION_EVERYONE
CHANNELS = [
    {"id": "880000111", "name": "mining-pings", "type": 0},
    {"id": "880000222", "name": "news", "type": 5},
    {"id": "880000333", "name": "Voice", "type": 2},
]


def fake_discord(client, *, everyone=ALL_NEEDED, overwrites=()):
    """The bot's view of the corporation's server: @everyone allows
    ``everyone``, the channel has ``overwrites``."""
    api = client.return_value
    channels = [
        dict(c, permission_overwrites=list(overwrites)) for c in CHANNELS
    ]
    api.get_guild_channels_raw.return_value = channels
    api.get_roles.return_value = [
        {"id": str(GUILD_ID), "permissions": str(everyone)}
    ]
    api.get_current_user.return_value = {"id": BOT_ID}
    api.get_guild_member_raw.return_value = {"roles": []}
    return api


@override_settings(DISCORD_GUILD_ID=1)
class CorporationFleetFollowTests(TestCase):
    def setUp(self):
        super().setUp()
        for uid in (
            "populate_eve_character_public_data",
            "populate_eve_character_private_data",
        ):
            signals.post_save.disconnect(sender=EveCharacter, dispatch_uid=uid)
        self.ceo = EveCharacter.objects.create(
            character_id=2001, character_name="Ceo", user=self.user
        )
        alliance = EveAlliance.objects.create(
            alliance_id=MINMATAR_FLEET_ASSOCIATES_ALLIANCE_ID,
            name="Associates",
        )
        self.corporation = EveCorporation.objects.create(
            corporation_id=98838663,
            name="M-EXC",
            ceo=self.ceo,
            alliance=alliance,
            discord_guild=DiscordGuild.objects.create(
                guild_id=GUILD_ID, name="M-EXC"
            ),
            discord_bot_status=EveCorporation.DISCORD_BOT_OK,
        )
        self.group = make_tribe_group(name="Mining", code="industry.mining")
        self.member = User.objects.create(username="member")

    def call(self, method, path="", user=None, data=None):
        kwargs = {
            "HTTP_AUTHORIZATION": f"Bearer {make_token(user or self.user)}"
        }
        if data is not None:
            kwargs["data"] = data
            kwargs["content_type"] = "application/json"
        url = f"{BASE_URL}/98838663/discord/fleet-follows{path}"
        return getattr(Client(), method)(url, **kwargs)

    def request_follow(self, channel_id="880000111", user=None):
        return self.call(
            "put", f"/{self.group.id}", user, {"channel_id": channel_id}
        )

    @patch(CLIENT)
    def test_ceo_requests_follow(self, client):
        fake_discord(client)
        response = self.request_follow()
        self.assertEqual(response.status_code, 200, response.content)
        follow = TribeGroupCorporationFollow.objects.get()
        self.assertEqual(follow.status, "requested")
        self.assertEqual(follow.channel_id, 880000111)
        self.assertEqual(follow.channel_name, "mining-pings")
        self.assertEqual(follow.requested_by, self.user)
        body = response.json()
        self.assertTrue(body["bot_ready"])
        self.assertEqual(
            [c["id"] for c in body["channels"]], ["880000111", "880000222"]
        )
        row = body["follows"][0]
        self.assertEqual(row["group_name"], "Mining")
        self.assertEqual(row["status"], "requested")
        self.assertEqual(row["warnings"], [])
        self.assertIn(
            self.group.id,
            [g["tribe_group_id"] for g in body["followable_groups"]],
        )

    @patch(CLIENT)
    def test_director_can_request(self, client):
        fake_discord(client)
        director_user = User.objects.create(username="director")
        director = EveCharacter.objects.create(
            character_id=2002, character_name="Dir", user=director_user
        )
        self.corporation.directors.add(director)
        self.assertEqual(
            self.request_follow(user=director_user).status_code, 200
        )

    @patch(CLIENT)
    def test_member_403(self, client):
        fake_discord(client)
        self.assertEqual(
            self.request_follow(user=self.member).status_code, 403
        )
        self.assertEqual(self.call("get", user=self.member).status_code, 403)

    @patch(CLIENT)
    def test_public_corp_400(self, client):
        fake_discord(client)
        self.corporation.alliance = None
        self.corporation.save()
        response = self.request_follow()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "not_eligible")

    @patch(CLIENT)
    def test_bot_not_linked_400(self, client):
        fake_discord(client)
        self.corporation.discord_bot_status = (
            EveCorporation.DISCORD_BOT_REMOVED
        )
        self.corporation.save()
        response = self.request_follow()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "not_connected")
        body = self.call("get").json()
        self.assertFalse(body["bot_ready"])
        self.assertEqual(body["channels"], [])

    @patch(CLIENT)
    def test_channel_outside_guild_400(self, client):
        fake_discord(client)
        for channel_id in ("999", "880000333"):
            response = self.request_follow(channel_id)
            self.assertEqual(response.status_code, 400, channel_id)
            self.assertEqual(response.json()["detail"], "unknown_channel")
        self.assertFalse(TribeGroupCorporationFollow.objects.exists())

    @patch(CLIENT)
    def test_unknown_group_404(self, client):
        fake_discord(client)
        response = self.call(
            "put", "/999999", data={"channel_id": "880000111"}
        )
        self.assertEqual(response.status_code, 404)

    @patch(CLIENT)
    def test_changing_channel_resets_to_requested(self, client):
        fake_discord(client)
        self.request_follow()
        TribeGroupCorporationFollow.objects.update(status="approved")
        self.request_follow("880000111")
        self.assertEqual(
            TribeGroupCorporationFollow.objects.get().status, "approved"
        )
        self.request_follow("880000222")
        follow = TribeGroupCorporationFollow.objects.get()
        self.assertEqual(follow.status, "requested")
        self.assertEqual(follow.channel_name, "news")

    @patch(CLIENT)
    def test_delete_stops_forwarding(self, client):
        fake_discord(client)
        self.request_follow()
        response = self.call("delete", f"/{self.group.id}")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(TribeGroupCorporationFollow.objects.exists())
        self.assertEqual(response.json()["follows"], [])

    @patch(CLIENT)
    def test_warnings_for_missing_here(self, client):
        fake_discord(client, everyone=ALL_NEEDED & ~MENTION_EVERYONE)
        self.request_follow()
        row = self.call("get").json()["follows"][0]
        self.assertEqual(row["warnings"], ["no_here"])

    @patch(CLIENT)
    def test_warnings_cant_post(self, client):
        # The channel denies @everyone Send Messages.
        fake_discord(
            client,
            overwrites=[
                {
                    "id": str(GUILD_ID),
                    "type": 0,
                    "allow": "0",
                    "deny": str(SEND_MESSAGES),
                }
            ],
        )
        self.request_follow()
        row = self.call("get").json()["follows"][0]
        self.assertEqual(row["warnings"], ["cant_post"])

    def test_follow_warnings(self):
        self.assertEqual(follow_warnings(ALL_NEEDED), [])
        self.assertEqual(follow_warnings(None), [])
        self.assertEqual(follow_warnings(1 << 3), [])  # administrator
        self.assertEqual(
            follow_warnings(VIEW_CHANNEL | SEND_MESSAGES),
            ["no_embeds", "no_here"],
        )

    @override_settings(
        DISCORD_CLIENT_ID="client-1",
        DISCORD_CORP_BOT_REDIRECT_URL="https://api.example/cb",
    )
    def test_install_url_asks_send_and_here(self):
        url = authorize_url("state")
        permissions = int(url.split("permissions=")[1].split("&")[0])
        for bit in (SEND_MESSAGES, EMBED_LINKS, MENTION_EVERYONE):
            self.assertTrue(permissions & bit, bit)
