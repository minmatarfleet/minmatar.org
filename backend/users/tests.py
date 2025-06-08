from unittest.mock import patch

from django.conf import settings
from django.db.models import signals
from django.test import Client
from django.contrib.auth.models import User
from esi.models import Token

from app.test import TestCase
from discord.models import DiscordUser
from eveonline.models import EveCharacter, EveCorporation
from eveonline.helpers.characters import (
    set_primary_character,
    user_primary_character,
)

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
        character.corporation = corporation
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
                    "corporation_id": primary_character.corporation.corporation_id,
                    "corporation_name": primary_character.corporation.name,
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
            discord_request_mock.exchange_code.return_value = {
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
            discord_request_mock.exchange_code.return_value = {
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

            django_user = User.objects.filter(username=username).first()
            self.assertEqual(django_user, self.user)

            discord_user = DiscordUser.objects.filter(user=django_user).first()
            self.assertIsNotNone(discord_user)
            self.assertTrue(discord_user.is_down_under)
            self.assertEqual("http://after.gif", discord_user.avatar)

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
