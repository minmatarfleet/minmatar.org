import unittest
from unittest.mock import patch
from unittest.mock import Mock

from django.contrib.auth.models import User, Group
from django.test import SimpleTestCase

from app.test import TestCase
from discord.core import make_nickname
from discord.models import DiscordUser
from discord.views import discord_login_redirect


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


class DiscordTests(TestCase):
    """
    Django tests for Discord functionality.
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

    def test_discord_login_redirect(self):

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


if __name__ == "__main__":
    unittest.main()
