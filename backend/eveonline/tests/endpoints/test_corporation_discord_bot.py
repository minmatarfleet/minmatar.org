from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from django.contrib.auth.models import User
from django.db.models import signals
from django.test import Client, override_settings

from app.test import TestCase
from app.testing import make_token
from discord.client import DiscordError
from discord.models import DiscordGuild
from eveonline.helpers.corporations.discord_bot import link_guild
from eveonline.models import EveCharacter, EveCorporation

BASE_URL = "/api/eveonline/corporations/corporations"
CALLBACK = f"{BASE_URL}/discord/bot/callback"
EXCHANGE = (
    "eveonline.endpoints.corporations.get_corporation_discord_bot_callback."
    "DiscordClient.exchange_bot_code"
)
SETUP_TASK = (
    "eveonline.endpoints.corporations.get_corporation_discord_bot_callback."
    "refresh_corporation_discord_bot.delay"
)
RELEASE_TASK = (
    "eveonline.endpoints.corporations.get_corporation_discord_bot_callback."
    "release_corporation_discord_guild.delay"
)
GUILD = {
    "id": "4242",
    "name": "Rattini Tribe",
    "icon": "abc",
    "system_channel_id": "77",
}


@override_settings(
    DISCORD_CLIENT_ID="client-1",
    DISCORD_CORP_BOT_REDIRECT_URL="https://api.example/cb",
    WEB_LINK_URL="https://my.example",
    DISCORD_GUILD_ID=1,
)
class CorporationDiscordBotEndpointTestCase(TestCase):
    def setUp(self):
        super().setUp()
        for uid in (
            "populate_eve_character_public_data",
            "populate_eve_character_private_data",
        ):
            signals.post_save.disconnect(sender=EveCharacter, dispatch_uid=uid)
        self.client = Client()
        self.ceo = EveCharacter.objects.create(
            character_id=2001, character_name="Ceo", user=self.user
        )
        self.corporation = EveCorporation.objects.create(
            corporation_id=98726134, name="Rattini Tribe", ceo=self.ceo
        )
        self.member_user = User.objects.create(username="member")

    def connect(self, user=None):
        token = make_token(user or self.user)
        return self.client.get(
            f"{BASE_URL}/98726134/discord/bot/connect", {"token": token}
        )

    def callback(self, **params):
        return self.client.get(CALLBACK, params)

    def start(self):
        response = self.connect()
        self.assertEqual(302, response.status_code)
        query = parse_qs(urlparse(response["Location"]).query)
        return query["state"][0]

    def test_connect_sends_the_ceo_to_discord(self):
        response = self.connect()
        self.assertEqual(302, response.status_code)
        location = urlparse(response["Location"])
        self.assertEqual("discord.com", location.netloc)
        query = parse_qs(location.query)
        self.assertEqual(["bot"], query["scope"])
        self.assertEqual(["1025"], query["permissions"])

    def test_connect_needs_settings_access_and_configuration(self):
        self.assertEqual(403, self.connect(self.member_user).status_code)
        self.assertEqual(
            401,
            self.client.get(
                f"{BASE_URL}/98726134/discord/bot/connect"
            ).status_code,
        )
        with override_settings(DISCORD_CORP_BOT_REDIRECT_URL=""):
            response = self.connect()
        self.assertEqual(400, response.status_code)
        self.assertEqual("bot_not_configured", response.json()["detail"])

    @patch(RELEASE_TASK)
    @patch(SETUP_TASK)
    @patch(EXCHANGE, return_value=GUILD)
    def test_callback_links_the_server_and_queues_setup(
        self, exchange, setup, release
    ):
        state = self.start()
        response = self.callback(code="abc", state=state, guild_id="4242")
        self.assertEqual(302, response.status_code)
        self.assertEqual(
            "https://my.example/alliance/corporations/rattini-tribe/"
            "?discord_bot=connected#settings",
            response["Location"],
        )
        exchange.assert_called_once_with("abc", "https://api.example/cb")
        setup.assert_called_once_with(98726134)
        release.assert_not_called()
        self.corporation.refresh_from_db()
        self.assertEqual("pending", self.corporation.discord_bot_status)
        self.assertEqual(4242, self.corporation.discord_guild.guild_id)

        # The state is single use.
        response = self.callback(code="abc", state=state)
        self.assertIn(
            "discord_bot_error=session_expired", response["Location"]
        )

    @patch(SETUP_TASK)
    @patch(EXCHANGE)
    def test_callback_rejections(self, exchange, setup):
        response = self.callback(code="abc", state="forged")
        self.assertIn(
            "discord_bot_error=session_expired", response["Location"]
        )

        state = self.start()
        response = self.callback(error="access_denied", state=state)
        self.assertIn("discord_bot_error=denied", response["Location"])

        # The alliance Discord is turned away before the code is used.
        state = self.start()
        response = self.callback(code="abc", state=state, guild_id="1")
        self.assertIn(
            "discord_bot_error=alliance_server", response["Location"]
        )

        # ...and when the URL lied about it, after.
        exchange.return_value = {**GUILD, "id": "1"}
        state = self.start()
        response = self.callback(code="abc", state=state, guild_id="4242")
        self.assertIn(
            "discord_bot_error=alliance_server", response["Location"]
        )

        exchange.side_effect = DiscordError("nope")
        state = self.start()
        response = self.callback(code="abc", state=state)
        self.assertIn(
            "discord_bot_error=exchange_failed", response["Location"]
        )

        setup.assert_not_called()
        self.corporation.refresh_from_db()
        self.assertIsNone(self.corporation.discord_guild)

    @patch(SETUP_TASK)
    @patch(EXCHANGE, return_value=GUILD)
    def test_callback_rechecks_access(self, exchange, setup):
        state = self.start()
        # Lost the CEO role between leaving and coming back.
        self.corporation.ceo = None
        self.corporation.save()
        response = self.callback(code="abc", state=state)
        self.assertIn("discord_bot_error=not_allowed", response["Location"])
        exchange.assert_not_called()

    @patch(RELEASE_TASK)
    @patch(SETUP_TASK)
    @patch(EXCHANGE, return_value={**GUILD, "id": "5555"})
    def test_callback_releases_the_previous_server(
        self, exchange, setup, release
    ):
        link_guild(self.corporation, GUILD, self.user)
        self.corporation.discord_bot_invite_code = "old"
        self.corporation.save()
        state = self.start()
        self.callback(code="abc", state=state)
        release.assert_called_once_with(4242, "old")

    def test_disconnect_and_retry(self):
        token = make_token(self.user)
        auth = {"HTTP_AUTHORIZATION": f"Bearer {token}"}
        url = f"{BASE_URL}/98726134/discord/bot"

        response = self.client.post(url + "/refresh", **auth)
        self.assertEqual(400, response.status_code)

        link_guild(self.corporation, GUILD, self.user)
        self.corporation.discord_bot_status = "no_permission"
        self.corporation.save()
        with patch(
            "eveonline.endpoints.corporations."
            "post_corporation_discord_bot_refresh."
            "refresh_corporation_discord_bot.delay"
        ) as setup:
            response = self.client.post(url + "/refresh", **auth)
        self.assertEqual(200, response.status_code)
        self.assertEqual("pending", response.json()["bot"]["status"])
        setup.assert_called_once_with(98726134)

        with patch(
            "eveonline.endpoints.corporations.delete_corporation_discord_bot."
            "release_corporation_discord_guild.delay"
        ) as release:
            response = self.client.delete(url, **auth)
        self.assertEqual(200, response.status_code)
        self.assertFalse(response.json()["bot"]["connected"])
        release.assert_called_once_with(4242, "")
        self.assertTrue(DiscordGuild.objects.filter(guild_id=4242).exists())

        member = {
            "HTTP_AUTHORIZATION": f"Bearer {make_token(self.member_user)}"
        }
        self.assertEqual(403, self.client.delete(url, **member).status_code)

    def test_settings_report_the_bot(self):
        token = make_token(self.user)
        response = self.client.get(
            f"{BASE_URL}/98726134/discord",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(200, response.status_code)
        bot = response.json()["bot"]
        self.assertTrue(bot["available"])
        self.assertFalse(bot["connected"])
        self.assertIsNone(response.json()["page_source"])
