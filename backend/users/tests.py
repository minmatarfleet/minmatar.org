from unittest.mock import patch, MagicMock

from django.conf import settings
from django.db import connection
from django.db.models import signals
from django.test import Client
from django.contrib.auth.models import User
from esi.models import CallbackRedirect, Token

from app.test import TestCase
from discord.client import DiscordError
from discord.models import DiscordUser
from eveonline.models import EveCharacter, EveCorporation
from eveonline.helpers.characters import (
    set_primary_character,
    user_primary_character,
)
from users.helpers import LEGACY_MUMBLE_ACCESS_TABLE, offboard_user
from users.router import callback

# Create your tests here.
BASE_URL = "/api/users/"


class UserRouterTestCase(TestCase):
    """Test case for the user router endpoints."""

    def setUp(self):
        signals.post_save.disconnect(
            sender=EveCharacter,
            dispatch_uid="populate_eve_character_public_data",
        )

        signals.post_save.disconnect(
            sender=EveCharacter,
            dispatch_uid="populate_eve_character_private_data",
        )

        self.client = Client()

        super().setUp()

    def test_get_user_profile_success(self):
        user = self.user
        token = Token.objects.create(
            character_id=634915984,
            user=user,
        )
        character = EveCharacter.objects.create(
            character_id=634915984,
            character_name="Test Character",
            token=token,
        )

        corporation = EveCorporation.objects.create(
            corporation_id=98726134,
            name="Test Corporation",
        )
        character.corporation_id = corporation.corporation_id
        character.save()
        discord_user = DiscordUser.objects.create(
            user=user,
            id=123,
            discord_tag="test#1234",
            nickname="testy",
        )
        set_primary_character(user, character)
        primary_character = user_primary_character(user)

        response = self.client.get(
            f"{BASE_URL}{self.user.id}/profile",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "user_id": user.id,
                "username": user.username,
                "permissions": [],
                "is_superuser": user.is_superuser,
                "eve_character_profile": {
                    "character_id": primary_character.character_id,
                    "character_name": primary_character.character_name,
                    "corporation_id": primary_character.corporation_id,
                    "corporation_name": corporation.name,
                    "scopes": [],
                },
                "discord_user_profile": {
                    "id": discord_user.id,
                    "discord_tag": discord_user.discord_tag,
                    "avatar": f"https://cdn.discordapp.com/avatars/{discord_user.id}/{discord_user.avatar}.png",
                    "nickname": discord_user.nickname,
                },
            },
        )

    def test_discord_login_redirect_api_new(self):
        """Test the API login redirect"""

        username = "new_user"

        with patch("users.router.discord") as discord_request_mock:
            discord_request_mock.complete_oauth_login.return_value = {
                "id": 1000001,
                "username": username,
                "discriminator": "100",
                "avatar": "http://avatar.gif",
            }

            response = self.client.get(
                "/api/users/callback?code=20001",
            )

            self.assertEqual(response.status_code, 302)
            self.assertIn(
                "https://my.minmatar.org/auth/login?token=", response.url
            )
            discord_request_mock.complete_oauth_login.assert_called_once()

            new_django_user = User.objects.filter(username=username).first()
            self.assertIsNotNone(new_django_user)
            new_discord_user = DiscordUser.objects.filter(
                user=new_django_user
            ).first()
            self.assertIsNotNone(new_discord_user)
            self.assertEqual("http://avatar.gif", new_discord_user.avatar)

    def test_discord_login_redirect_api_existing(self):
        """Test the API login redirect"""

        username = self.user.username

        DiscordUser.objects.create(
            id=1000002,
            user=self.user,
            discord_tag=username,
            nickname=username,
            is_down_under=True,
            avatar="http://before.gif",
        )

        with patch("users.router.discord") as discord_request_mock:
            discord_request_mock.complete_oauth_login.return_value = {
                "id": 1000002,
                "username": username,
                "discriminator": "12345",
                "avatar": "http://after.gif",
            }

            response = self.client.get(
                "/api/users/callback?code=20002",
            )

            self.assertEqual(response.status_code, 302)
            self.assertIn(
                "https://my.minmatar.org/auth/login?token=", response.url
            )
            discord_request_mock.complete_oauth_login.assert_called_once()

            django_user = User.objects.filter(username=username).first()
            self.assertEqual(django_user, self.user)

            discord_user = DiscordUser.objects.filter(user=django_user).first()
            self.assertIsNotNone(discord_user)
            self.assertTrue(discord_user.is_down_under)
            self.assertEqual("http://after.gif", discord_user.avatar)

    @patch("users.router.discord.complete_oauth_login")
    def test_discord_login_redirect_error(self, oauth_mock):
        request = MagicMock()

        discord_response = MagicMock()
        discord_response.status_code = 400
        oauth_mock.side_effect = DiscordError.for_response(
            "Error exchanging token", "EXCHG_CODE", discord_response
        )
        response = callback(request, code="100001")
        self.assertEqual(response.status_code, 302)
        self.assertIn("error=EXCHG_CODE", response.url)

        oauth_mock.side_effect = DiscordError.for_response(
            "Error fetching Discord profile", "GET_PROFILE", discord_response
        )
        response = callback(request, code="100001")
        self.assertEqual(response.status_code, 302)
        self.assertIn("error=GET_PROFILE", response.url)

    def test_discord_login_guild_join_failure_does_not_create_user(self):
        username = "join_fail_user"
        discord_response = MagicMock()
        discord_response.status_code = 403
        join_error = DiscordError.for_response(
            "Error adding Discord guild member",
            "GUILD_JOIN",
            discord_response,
        )

        with patch("users.router.discord") as discord_request_mock:
            discord_request_mock.complete_oauth_login.side_effect = join_error

            response = self.client.get(
                "/api/users/callback?code=20003",
            )

        self.assertEqual(response.status_code, 302)
        self.assertIn("error=GUILD_JOIN", response.url)
        self.assertIn(f"id={join_error.id}", response.url)
        self.assertFalse(User.objects.filter(username=username).exists())
        discord_request_mock.complete_oauth_login.assert_called_once()

    def test_login_requests_guilds_join_scope(self):
        fake_user = settings.FAKE_LOGIN_USER_ID
        del settings.FAKE_LOGIN_USER_ID

        response = self.client.get(
            "/api/users/login?redirect_url=abc123",
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("scope=identify%20guilds.join", response.url)
        self.assertEqual(
            "abc123", self.client.session["authentication_redirect_url"]
        )

        settings.FAKE_LOGIN_USER_ID = fake_user

    def test_discord_login_no_code(self):
        request = MagicMock()

        response = callback(
            request,
            code=None,
            error="access_denied",
            error_description="The resource owner or authorization server denied the request",
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("error=DENIED", response.url)

    def test_login(self):
        fake_user = settings.FAKE_LOGIN_USER_ID
        del settings.FAKE_LOGIN_USER_ID

        response = self.client.get(
            "/api/users/login?redirect_url=abc123",
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            "abc123", self.client.session["authentication_redirect_url"]
        )

        settings.FAKE_LOGIN_USER_ID = fake_user

    def test_eve_mobile_complete_linked_character(self):
        esi_token = Token.objects.create(
            character_id=634915984,
            character_name="BearThatCares",
            user=self.user,
        )
        character = EveCharacter.objects.create(
            character_id=634915984,
            character_name="BearThatCares",
            token=esi_token,
            user=self.user,
        )
        set_primary_character(self.user, character)

        session = self.client.session
        session["authentication_redirect_url"] = "mobile://auth/callback"
        session.save()

        CallbackRedirect.objects.create(
            session_key=session.session_key,
            state="test-state",
            url="/api/users/eve/complete/",
            token=esi_token,
        )

        response = self.client.get("/api/users/eve/complete/")

        self.assertEqual(response.status_code, 302)
        self.assertIn("mobile://auth/callback?token=", response.url)

    def test_eve_mobile_complete_character_only(self):
        esi_token = Token.objects.create(
            character_id=2117059479,
            character_name="MiniSpartan",
        )

        session = self.client.session
        session["authentication_redirect_url"] = "mobile://auth/callback"
        session.save()

        CallbackRedirect.objects.create(
            session_key=session.session_key,
            state="test-state",
            url="/api/users/eve/complete/",
            token=esi_token,
        )

        response = self.client.get("/api/users/eve/complete/")

        self.assertEqual(response.status_code, 302)
        self.assertIn("mobile://auth/callback?token=", response.url)

    def test_eve_login_start_redirect(self):
        settings.ESI_SSO_CLIENT_ID = "test-client-id"
        settings.ESI_SSO_CALLBACK_URL = "http://testserver/sso/callback"

        response = self.client.get(
            "/api/users/login/eve?redirect_url=mobile://auth/callback"
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("login.eveonline.com/v2/oauth/authorize", response.url)
        self.assertEqual(
            "mobile://auth/callback",
            self.client.session["authentication_redirect_url"],
        )


class OffboardUserTestCase(TestCase):
    """Offboard must succeed even with leftover mumble_mumbleaccess rows."""

    def _create_legacy_mumble_table(self):
        quoted = connection.ops.quote_name(LEGACY_MUMBLE_ACCESS_TABLE)
        with connection.cursor() as cursor:
            cursor.execute(f"""
                CREATE TABLE {quoted} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    username VARCHAR(255) NOT NULL,
                    password VARCHAR(255) NOT NULL,
                    suspended BOOLEAN NOT NULL DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES auth_user (id)
                )
                """)

    def _drop_legacy_mumble_table(self):
        quoted = connection.ops.quote_name(LEGACY_MUMBLE_ACCESS_TABLE)
        with connection.cursor() as cursor:
            cursor.execute(f"DROP TABLE IF EXISTS {quoted}")

    def tearDown(self):
        self._drop_legacy_mumble_table()
        super().tearDown()

    def test_offboard_deletes_user_with_legacy_mumble_access_row(self):
        self._create_legacy_mumble_table()
        quoted = connection.ops.quote_name(LEGACY_MUMBLE_ACCESS_TABLE)
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                INSERT INTO {quoted} (user_id, username, password, suspended)
                VALUES (%s, %s, %s, %s)
                """,
                [self.user.id, "Test Char", "secret", False],
            )

        offboard_user(self.user.id)

        self.assertFalse(User.objects.filter(id=self.user.id).exists())
