from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from requests.exceptions import HTTPError

from discord.client import (
    DISCORD_OAUTH_SCOPES,
    DiscordClient,
    DiscordError,
    discord_authorize_url,
)


class DiscordOAuthLoginTests(SimpleTestCase):
    def test_discord_authorize_url_includes_guilds_join(self):
        url = discord_authorize_url("client-1", "http://localhost/callback")
        self.assertIn("client_id=client-1", url)
        self.assertIn("redirect_uri=http://localhost/callback", url)
        self.assertIn("scope=identify%20guilds.join", url)

    @patch("discord.client.requests.post")
    @patch("discord.client.requests.get")
    def test_exchange_code_returns_profile_and_access_token(
        self, get_mock, post_mock
    ):
        post_mock.return_value = MagicMock(
            status_code=200,
            json=lambda: {"access_token": "user-token"},
        )
        get_mock.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "id": "99",
                "username": "pilot",
                "discriminator": "0",
            },
        )
        with patch("discord.client._assert_discord_http_allowed"):
            user, token = DiscordClient().exchange_code(
                "code", "http://localhost/callback"
            )
        self.assertEqual(token, "user-token")
        self.assertEqual(user["username"], "pilot")
        self.assertEqual(
            post_mock.call_args.kwargs["data"]["scope"], DISCORD_OAUTH_SCOPES
        )

    def test_add_guild_member_success(self):
        client = DiscordClient()
        with patch.object(client, "put") as put_mock:
            put_mock.return_value = MagicMock(status_code=201)
            client.add_guild_member(123, "user-token")
        put_mock.assert_called_once()
        args, kwargs = put_mock.call_args
        self.assertIn("/members/123", args[0])
        self.assertEqual(kwargs["json"]["access_token"], "user-token")

    def test_add_guild_member_http_error_raises_guild_join(self):
        client = DiscordClient()
        response = MagicMock()
        response.status_code = 403
        http_error = HTTPError(response=response)
        http_error.response = response
        with patch.object(client, "put", side_effect=http_error):
            with self.assertRaises(DiscordError) as ctx:
                client.add_guild_member(123, "user-token")
        self.assertEqual(ctx.exception.code, "GUILD_JOIN")
        self.assertEqual(ctx.exception.status_code, 403)

    def test_complete_oauth_login_exchanges_and_joins(self):
        client = DiscordClient()
        profile = {"id": "99", "username": "pilot"}
        with patch.object(
            client, "exchange_code", return_value=(profile, "token")
        ) as exchange_mock:
            with patch.object(client, "add_guild_member") as join_mock:
                user = client.complete_oauth_login(
                    "code", "http://localhost/callback"
                )
        self.assertEqual(user, profile)
        exchange_mock.assert_called_once_with(
            "code", "http://localhost/callback"
        )
        join_mock.assert_called_once_with("99", "token")

    def test_complete_oauth_login_propagates_join_failure(self):
        client = DiscordClient()
        profile = {"id": "99", "username": "pilot"}
        discord_response = MagicMock()
        discord_response.status_code = 403
        join_error = DiscordError.for_response(
            "Error adding Discord guild member",
            "GUILD_JOIN",
            discord_response,
        )
        with patch.object(
            client, "exchange_code", return_value=(profile, "token")
        ):
            with patch.object(
                client, "add_guild_member", side_effect=join_error
            ):
                with self.assertRaises(DiscordError) as ctx:
                    client.complete_oauth_login(
                        "code", "http://localhost/callback"
                    )
        self.assertEqual(ctx.exception.code, "GUILD_JOIN")
