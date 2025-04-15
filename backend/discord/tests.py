import unittest
from unittest.mock import patch
from unittest.mock import Mock

from django.contrib.auth.models import User, Group
from django.test import SimpleTestCase
from django.db.models import signals

from eveonline.models import (
    EveCharacter,
    EvePrimaryCharacter,
    EvePrimaryCharacterChangeLog,
    EveCorporation,
)

from app.test import TestCase
from discord.core import make_nickname
from discord.models import DiscordUser
from discord.views import discord_login_redirect
from discord.tasks import sync_discord_nickname


class DiscordSimpleTests(SimpleTestCase):
    """
    Unit tests for Discord functionality.
    """

    def test_basic_nickname(self):
        character = Mock(character_name="Bob", corporation=Mock(ticker="ABC"))
        discord = Mock(is_down_under=False, dress_wearer=False)
        self.assertEqual("[ABC] Bob", make_nickname(character, discord))

    def test_down_under_nickname(self):
        character = Mock(character_name="Bob", corporation=Mock(ticker="ABC"))
        discord = Mock(is_down_under=True, dress_wearer=False)
        self.assertEqual("qoᗺ [ƆᗺⱯ]", make_nickname(character, discord))

    def test_dress_wearer(self):
        character = Mock(character_name="Bob", corporation=Mock(ticker="ABC"))
        discord = Mock(is_down_under=False, dress_wearer=True)
        self.assertEqual("[👗] Bob", make_nickname(character, discord))

    def test_dry_corp(self):
        character = Mock(
            character_name="Scott", corporation=Mock(ticker="-DRY-")
        )
        discord = Mock(is_down_under=False, dress_wearer=True)
        self.assertEqual("[ω] Scott", make_nickname(character, discord))


class DiscordSignalTests(TestCase):
    """
    Django tests for Discord signal functionality.
    """

    def test_user_group_change_signals(self):
        with patch("discord.signals.discord") as discord_mock:
            discord_mock.get_roles.return_value = []
            discord_mock.create_role.return_value.json.return_value = {
                "id": 1,
            }

            DiscordUser.objects.create(
                id=1,
                discord_tag="tag",
                user=self.user,
            )
            group = Group.objects.create(name="testgroup")

            self.user.groups.add(group)

            discord_mock.get_roles.assert_called()
            discord_mock.create_role.assert_called_with("testgroup")


class DiscordTests(TestCase):
    """
    Django tests for Discord functionality.
    """

    def test_discord_login_redirect_admin(self):
        """Test the admin page login redirect"""

        with patch("discord.views.login"):
            with patch("discord.views.requests") as discord_request_mock:
                mock_post_response = Mock(
                    data="data",
                    status_code=200,
                )
                discord_request_mock.post.return_value = mock_post_response
                mock_post_response.json.return_value = {
                    "access_token": "ABC123",
                }

                mock_get_response = Mock(
                    data="data",
                    status_code=200,
                )
                discord_request_mock.get.return_value = mock_get_response
                mock_get_response.json.return_value = {
                    "id": 12345,
                    "username": "testuser",
                    "discriminator": "123",
                    "avatar": "http://avatar.gif",
                }

                redirect_request_mock = Mock()
                redirect_request_mock.GET.get.return_value = None
                redirect_request_mock.session = {}

                discord_login_redirect(redirect_request_mock)

        new_django_user = User.objects.filter(username="testuser").first()
        self.assertIsNotNone(new_django_user)
        new_discord_user = DiscordUser.objects.filter(
            user=new_django_user
        ).first()
        self.assertIsNotNone(new_discord_user)
        self.assertEqual("http://avatar.gif", new_discord_user.avatar)

    def test_discord_nickname_task(self):
        signals.post_save.disconnect(
            sender=EveCharacter,
            dispatch_uid="populate_eve_character_public_data",
        )
        signals.post_save.disconnect(
            sender=EveCharacter,
            dispatch_uid="populate_eve_character_private_data",
        )
        signals.post_save.disconnect(
            sender=EvePrimaryCharacterChangeLog,
            dispatch_uid="notify_people_team_of_primary_character_change",
        )
        signals.post_save.disconnect(
            sender=Group,
            dispatch_uid="group_post_save",
        )

        DiscordUser.objects.create(id=1, user=self.user)
        corp = EveCorporation.objects.create(
            corporation_id=123,
            introduction="",
            biography="",
            timezones="",
            requirements="",
            name="TestCorp",
            ticker="CORP",
        )
        char = EveCharacter.objects.create(
            character_id=123,
            character_name="Test Char",
            corporation=corp,
        )
        EvePrimaryCharacter.objects.create(
            user=self.user,
            character=char,
        )
        group, _ = Group.objects.get_or_create(name="Alliance")
        self.user.groups.add(group)

        with patch("discord.tasks.discord") as discord_mock:
            sync_discord_nickname(self.user, force_update=True)

            discord_mock.update_user.assert_called()


if __name__ == "__main__":
    unittest.main()
