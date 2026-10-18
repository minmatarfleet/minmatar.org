from unittest.mock import patch, MagicMock

import jwt

from django.conf import settings
from django.db import connection
from django.db.models import signals
from django.test import Client, override_settings
from django.contrib.auth.models import User
from esi.models import CallbackRedirect, Token

from app.test import TestCase
from discord.client import DiscordError
from discord.models import DiscordChannelActivityRecord, DiscordUser
from eveonline.models import EveCharacter, EveCorporation, EvePlayer
from eveonline.helpers.characters import (
    set_primary_character,
    user_primary_character,
)
from users.helpers import (
    LEGACY_MUMBLE_ACCESS_TABLE,
    make_user_objects,
    offboard_user,
)
from users.models import UserDesktopSettings
from users.redirects import is_allowed_login_redirect, oauth_redirect
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
                "community_status": None,
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
            "/api/users/login?redirect_url=https://my.minmatar.org/auth/login",
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("scope=identify%20guilds.join", response.url)
        self.assertEqual(
            "https://my.minmatar.org/auth/login",
            self.client.session["authentication_redirect_url"],
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
            "/api/users/login?redirect_url=https://my.minmatar.org/auth/login",
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            "https://my.minmatar.org/auth/login",
            self.client.session["authentication_redirect_url"],
        )

        settings.FAKE_LOGIN_USER_ID = fake_user

    def test_desktop_loopback_login_round_trip(self):
        """The desktop app's sign-in contract: login with a loopback
        redirect_url, Discord callback lands back on it with a usable JWT."""
        fake_user = settings.FAKE_LOGIN_USER_ID
        del settings.FAKE_LOGIN_USER_ID
        loopback = "http://127.0.0.1:53123/callback/0123456789abcdef"

        try:
            response = self.client.get(
                "/api/users/login",
                {"redirect_url": loopback},
            )
            self.assertEqual(response.status_code, 302)

            with patch("users.router.discord") as discord_request_mock:
                discord_request_mock.complete_oauth_login.return_value = {
                    "id": 1000003,
                    "username": "desktop_user",
                    "discriminator": "0",
                    "avatar": "abc",
                }
                response = self.client.get("/api/users/callback?code=20004")
        finally:
            settings.FAKE_LOGIN_USER_ID = fake_user

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(f"{loopback}?token="))
        token = response.url.split("?token=", 1)[1]

        me = self.client.get(
            "/api/users/me", HTTP_AUTHORIZATION=f"Bearer {token}"
        )
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["username"], "desktop_user")

    def test_eve_mobile_complete_linked_character(self):
        esi_token = Token.objects.create(
            character_id=634915984,
            character_name="BearThatCares",
            character_owner_hash="owner-a",
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


class DesktopSettingsTestCase(TestCase):
    """Desktop app settings saved on the account."""

    URL = "/api/users/me/desktop-settings"

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="desktop_pilot")
        token = jwt.encode(
            {"user_id": self.user.id}, settings.SECRET_KEY, algorithm="HS256"
        )
        self.auth = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def patch_values(self, values, **extra):
        return self.client.patch(
            self.URL,
            {"values": values},
            content_type="application/json",
            **{**self.auth, **extra},
        )

    def test_requires_sign_in(self):
        self.assertEqual(self.client.get(self.URL).status_code, 401)
        self.assertEqual(
            self.client.patch(
                self.URL, {"values": {}}, content_type="application/json"
            ).status_code,
            401,
        )

    def test_empty_until_first_save(self):
        response = self.client.get(self.URL, **self.auth)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"values": {}, "updated_at": None})
        self.assertFalse(UserDesktopSettings.objects.exists())

    def test_patch_merges_keys_and_null_removes(self):
        bounds = {"x": 10, "y": 20, "width": 380, "height": 520}
        self.patch_values(
            {"show_sneak": False, "window.fleets": {"bounds": bounds}}
        )
        response = self.patch_values(
            {"only_over_eve": True, "show_sneak": None}
        )
        self.assertEqual(response.status_code, 200)
        expected = {
            "window.fleets": {"bounds": bounds},
            "only_over_eve": True,
        }
        self.assertEqual(response.json()["values"], expected)
        self.assertEqual(
            self.client.get(self.URL, **self.auth).json()["values"], expected
        )

    def test_settings_are_per_user(self):
        self.patch_values({"show_sneak": False})
        other = User.objects.create_user(username="someone_else")
        token = jwt.encode(
            {"user_id": other.id}, settings.SECRET_KEY, algorithm="HS256"
        )
        response = self.client.get(
            self.URL, HTTP_AUTHORIZATION=f"Bearer {token}"
        )
        self.assertEqual(response.json()["values"], {})

    def test_rejects_oversized_settings(self):
        response = self.patch_values({"x" * 65: 1})
        self.assertEqual(response.status_code, 400)
        response = self.patch_values({f"k{i}": i for i in range(101)})
        self.assertEqual(response.status_code, 400)
        response = self.patch_values({"big": "x" * 33_000})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            self.client.get(self.URL, **self.auth).json()["values"], {}
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


class MakeUserObjectsTestCase(TestCase):
    """Login must not fail when EvePlayer nicknames collide case-insensitively."""

    def test_eve_player_created_when_nickname_case_collides(self):
        owner = User.objects.create(username="AdminDude")
        EvePlayer.objects.create(user=owner, nickname="BearThatCares")

        django_user = make_user_objects(
            {
                "id": 999001,
                "username": "bearthatcares",
                "discriminator": "0",
                "avatar": "abc",
            }
        )

        player = EvePlayer.objects.get(user=django_user)
        self.assertEqual(player.nickname, f"bearthatcares__u{django_user.pk}")
        self.assertNotEqual(player.user_id, owner.id)

    def test_eve_player_reuses_existing_for_same_user(self):
        django_user = make_user_objects(
            {
                "id": 999002,
                "username": "freshpilot",
                "discriminator": "0",
                "avatar": "abc",
            }
        )
        first = EvePlayer.objects.get(user=django_user)

        again = make_user_objects(
            {
                "id": 999002,
                "username": "freshpilot",
                "discriminator": "0",
                "avatar": "def",
            }
        )

        self.assertEqual(again.id, django_user.id)
        self.assertEqual(EvePlayer.objects.filter(user=again).count(), 1)
        self.assertEqual(
            EvePlayer.objects.get(user=again).nickname, first.nickname
        )


def _discord_profile(discord_id, username):
    return {
        "id": discord_id,
        "username": username,
        "discriminator": "0",
        "avatar": "abc",
    }


class DiscordLoginIdentityTestCase(TestCase):
    """The Discord ID picks the account; a username never does."""

    def test_rename_keeps_the_same_account(self):
        original = make_user_objects(_discord_profile(5001, "alice"))
        EveCharacter.objects.create(
            character_id=91001, character_name="Alice Main", user=original
        )

        renamed = make_user_objects(_discord_profile(5001, "alice2"))

        self.assertEqual(renamed.id, original.id)
        self.assertEqual(renamed.username, "alice2")
        self.assertEqual(User.objects.filter(username="alice").count(), 0)
        self.assertEqual(
            EveCharacter.objects.get(character_id=91001).user_id, original.id
        )
        self.assertEqual(DiscordUser.objects.get(id=5001).user_id, original.id)

    def test_released_username_does_not_open_previous_owners_account(self):
        victim = User.objects.create(username="alice", is_superuser=True)
        DiscordUser.objects.create(id=5001, user=victim, discord_tag="alice#0")

        claimer = make_user_objects(_discord_profile(6002, "alice"))

        self.assertNotEqual(claimer.id, victim.id)
        self.assertFalse(claimer.is_superuser)
        self.assertEqual(DiscordUser.objects.get(id=5001).user_id, victim.id)
        self.assertEqual(DiscordUser.objects.get(id=6002).user_id, claimer.id)

    def test_account_without_discord_link_is_not_handed_over(self):
        # The state the old code left behind after a rename: characters on
        # an account no DiscordUser points at.
        stranded = User.objects.create(username="alice")
        EveCharacter.objects.create(
            character_id=91002, character_name="Stranded", user=stranded
        )

        claimer = make_user_objects(_discord_profile(6003, "alice"))

        self.assertNotEqual(claimer.id, stranded.id)
        self.assertEqual(
            EveCharacter.objects.get(character_id=91002).user_id, stranded.id
        )

    def test_case_variant_of_existing_username_gets_its_own_account(self):
        other = User.objects.create(username="Alice")
        DiscordUser.objects.create(id=5004, user=other, discord_tag="Alice#0")

        claimer = make_user_objects(_discord_profile(6004, "alice"))

        self.assertNotEqual(claimer.id, other.id)
        self.assertTrue(claimer.username.startswith("alice__d"))

    def test_rename_onto_a_stale_accounts_name_keeps_current_username(self):
        stale = User.objects.create(username="bob")
        DiscordUser.objects.create(id=5005, user=stale, discord_tag="bob#0")
        mover = make_user_objects(_discord_profile(6005, "carol"))

        again = make_user_objects(_discord_profile(6005, "bob"))

        self.assertEqual(again.id, mover.id)
        self.assertEqual(again.username, "carol")
        self.assertEqual(User.objects.get(id=stale.id).username, "bob")


class DiscordLoginRenameAndRaceTestCase(TestCase):
    def test_rename_moves_voice_minutes_with_the_pilot(self):
        pilot = make_user_objects(_discord_profile(7001, "alice"))
        DiscordChannelActivityRecord.objects.create(
            activity_type=DiscordChannelActivityRecord.VOICE_MINUTE,
            username="alice",
            quantity=90,
            channel_id=1,
            channel_name="Fleet 1",
        )

        make_user_objects(_discord_profile(7001, "alice2"))
        newcomer = make_user_objects(_discord_profile(7002, "alice"))

        self.assertEqual(newcomer.username, "alice")
        self.assertFalse(
            DiscordChannelActivityRecord.objects.filter(
                username="alice"
            ).exists()
        )
        self.assertEqual(
            DiscordChannelActivityRecord.objects.get().username,
            User.objects.get(id=pilot.id).username,
        )

    def test_concurrent_first_login_reuses_the_winning_account(self):
        winner = User.objects.create(username="racer")
        DiscordUser.objects.create(id=7003, user=winner, discord_tag="racer#0")
        users_before = User.objects.count()
        real_filter = DiscordUser.objects.filter
        calls = {"n": 0}

        def first_lookup_misses(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                return DiscordUser.objects.none()
            return real_filter(*args, **kwargs)

        with patch.object(
            DiscordUser.objects, "filter", side_effect=first_lookup_misses
        ):
            result = make_user_objects(_discord_profile(7003, "racer"))

        self.assertEqual(result.id, winner.id)
        self.assertEqual(User.objects.count(), users_before)


class LoginRedirectAllowlistTestCase(TestCase):
    """Logins append ?token=<JWT>, so they may only redirect to our own apps."""

    def setUp(self):
        super().setUp()
        self.fake_user = settings.FAKE_LOGIN_USER_ID
        del settings.FAKE_LOGIN_USER_ID

    def tearDown(self):
        settings.FAKE_LOGIN_USER_ID = self.fake_user
        super().tearDown()

    def _discord_login(self, redirect_url):
        self.client.get("/api/users/login", {"redirect_url": redirect_url})
        with patch("users.router.discord") as discord_request_mock:
            discord_request_mock.complete_oauth_login.return_value = {
                "id": 1000077,
                "username": "redirect_user",
                "discriminator": "0",
                "avatar": "abc",
            }
            return self.client.get("/api/users/callback?code=20077")

    def test_offsite_redirect_never_receives_the_token(self):
        response = self._discord_login("https://evil.example/steal")

        self.assertEqual(response.status_code, 302)
        self.assertNotIn("evil.example", response.url)
        self.assertTrue(
            response.url.startswith(
                f"{settings.WEB_LINK_URL.rstrip('/')}/auth/login?token="
            )
        )

    def test_tampered_session_redirect_falls_back_at_callback(self):
        self.client.get(
            "/api/users/login",
            {"redirect_url": "https://my.minmatar.org/auth/login"},
        )
        session = self.client.session
        session["authentication_redirect_url"] = "https://evil.example/"
        session.save()
        with patch("users.router.discord") as discord_request_mock:
            discord_request_mock.complete_oauth_login.return_value = {
                "id": 1000078,
                "username": "tamper_user",
                "discriminator": "0",
                "avatar": "abc",
            }
            response = self.client.get("/api/users/callback?code=20078")

        self.assertNotIn("evil.example", response.url)

    def test_website_redirect_is_kept(self):
        response = self._discord_login("https://my.minmatar.org/friend/login")

        self.assertTrue(
            response.url.startswith(
                "https://my.minmatar.org/friend/login?token="
            )
        )

    @override_settings(
        ESI_SSO_CLIENT_ID="test-client",
        ESI_SSO_CALLBACK_URL="https://my.minmatar.org/sso/callback",
    )
    def test_eve_login_refuses_offsite_redirect(self):
        self.client.get(
            "/api/users/login/eve",
            {"redirect_url": "https://evil.example/cb"},
        )
        self.assertEqual(
            self.client.session.get("authentication_redirect_url"),
            "mobile://auth/callback",
        )

    def test_eve_completion_ignores_offsite_session_redirect(self):
        esi_token = Token.objects.create(
            character_id=91077, character_name="Redirect Pilot"
        )
        session = self.client.session
        session["authentication_redirect_url"] = "https://evil.example/"
        session.save()
        CallbackRedirect.objects.create(
            session_key=session.session_key,
            state="redirect-state",
            url="/api/users/eve/complete/",
            token=esi_token,
        )

        response = self.client.get("/api/users/eve/complete/")

        self.assertEqual(response.status_code, 302)
        self.assertNotIn("evil.example", response.url)
        self.assertTrue(response.url.startswith("mobile://auth/callback?"))


class IsAllowedLoginRedirectTestCase(TestCase):
    def test_allowed(self):
        for url in [
            "https://my.minmatar.org/auth/login",
            "https://my.minmatar.org/friend/login",
            "http://localhost:4321/auth/login",
            "http://127.0.0.1:53123/callback/0123456789abcdef",
            "http://[::1]:5000/callback/x",
            "mobile://auth/callback",
            "minmatar://auth/callback",
            "exp://192.168.1.20:8081/--/auth/callback",
        ]:
            self.assertTrue(is_allowed_login_redirect(url), url)

    def test_refused(self):
        for url in [
            "",
            None,
            "abc123",
            "/auth/login",
            "//evil.example/x",
            "https://evil.example/x",
            "https://my.minmatar.org.evil.example/x",
            "https://evil.example#@my.minmatar.org",
            "https://my.minmatar.org@evil.example/x",
            "https://user:pw@my.minmatar.org/x",
            "http://my.minmatar.org/auth/login",
            "https://localhost.evil.example/x",
            "https://127.0.0.1/x",
            "javascript:alert(1)",
            "data:text/html,hi",
            "exp://evil.example:8081/--/auth/callback",
            "exp://8.8.8.8:8081/--/auth/callback",
            # Not a scheme the deep-link redirect can serve.
            "exps://192.168.1.20:8081/--/auth/callback",
        ]:
            self.assertFalse(is_allowed_login_redirect(url), url)

    def test_every_allowed_redirect_can_be_served(self):
        for url in [
            "https://my.minmatar.org/auth/login",
            "http://localhost:4321/auth/login",
            "http://127.0.0.1:53123/callback/0123456789abcdef",
            "mobile://auth/callback",
            "minmatar://auth/callback",
            "exp://192.168.1.20:8081/--/auth/callback",
        ]:
            self.assertTrue(is_allowed_login_redirect(url), url)
            response = oauth_redirect(f"{url}?token=t")
            self.assertEqual(302, response.status_code, url)
            self.assertEqual(f"{url}?token=t", response.url, url)
