import unittest
from unittest.mock import patch, Mock, MagicMock

from django.contrib.auth.models import User, Group
from django.test import SimpleTestCase
from django.db.models import signals

from eveonline.models import (
    EveCharacter,
    EveCorporation,
)
from eveonline.helpers.characters import set_primary_character

from app.test import TestCase
from discord.core import make_nickname
from discord.models import DiscordUser, DiscordRole
from discord.views import discord_login_redirect, fake_login

from discord.tasks import sync_discord_nickname, sync_discord_user
from discord.helpers import (
    remove_all_roles_from_guild_member,
    find_unregistered_guild_members,
)

from requests.exceptions import HTTPError


class DiscordSimpleTests(SimpleTestCase):
    """
    Unit tests for Discord functionality.
    """

    def test_basic_nickname(self):
        character = Mock(character_name="Bob", corporation=Mock(ticker="ABC"))
        discord = Mock(is_down_under=False, dress_wearer=False)
        self.assertEqual("[ABC] Bob", make_nickname(character, discord))


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

    @patch("discord.helpers.DiscordUser")
    @patch("discord.helpers.discord")
    def test_find_unregistered_guild_members_some_unregistered(
        self, mock_discord, mock_discord_user
    ):
        # member2 is not registered, member3 is a bot and should be excluded
        member1 = {"user": {"id": 1}}
        member2 = {"user": {"id": 2}}
        member3 = {"user": {"id": 3, "bot": True}}
        mock_discord.get_members.return_value = [member1, member2, member3]
        # Only member1 and member3 are registered
        mock_discord_user.objects.values_list.return_value = [1, 3]
        result = find_unregistered_guild_members()
        self.assertEqual(result, [member2])

    @patch("discord.helpers.DiscordUser")
    @patch("discord.helpers.discord")
    def test_find_unregistered_guild_members_all_registered(
        self, mock_discord, mock_discord_user
    ):
        member1 = {"user": {"id": 1}}
        member2 = {"user": {"id": 2, "bot": True}}
        mock_discord.get_members.return_value = [member1, member2]
        mock_discord_user.objects.values_list.return_value = [1, 2]
        result = find_unregistered_guild_members()
        self.assertEqual(result, [])

    @patch("discord.helpers.DiscordUser")
    @patch("discord.helpers.discord")
    def test_find_unregistered_guild_members_none_registered(
        self, mock_discord, mock_discord_user
    ):
        member1 = {"user": {"id": 1}}
        member2 = {"user": {"id": 2, "bot": True}}
        member3 = {"user": {"id": 3}}
        mock_discord.get_members.return_value = [member1, member2, member3]
        mock_discord_user.objects.values_list.return_value = []
        result = find_unregistered_guild_members()
        # Only non-bots should be returned
        self.assertEqual(result, [member1, member3])

    @patch("discord.helpers.DiscordUser")
    @patch("discord.helpers.discord")
    def test_find_unregistered_guild_members_empty_guild(
        self, mock_discord, mock_discord_user
    ):
        mock_discord.get_members.return_value = []
        mock_discord_user.objects.values_list.return_value = [1, 2]
        result = find_unregistered_guild_members()
        self.assertEqual(result, [])

    def disconnect_signals(self):
        signals.post_save.disconnect(
            sender=EveCharacter,
            dispatch_uid="populate_eve_character_public_data",
        )
        signals.post_save.disconnect(
            sender=EveCharacter,
            dispatch_uid="populate_eve_character_private_data",
        )
        signals.post_save.disconnect(
            sender=Group,
            dispatch_uid="group_post_save",
        )
        signals.pre_save.disconnect(
            sender=DiscordRole,
            dispatch_uid="resolve_existing_discord_role_from_server",
        )
        signals.post_save.disconnect(
            sender=Group,
            dispatch_uid="group_post_save",
        )
        signals.m2m_changed.disconnect(
            sender=User.groups.through,
            dispatch_uid="user_group_changed",
        )

    def test_discord_login_redirect_admin(self):
        """Test the admin page login redirect"""

        with patch("discord.views.login"):
            with patch("discord.views.discord") as discord_client_mock:
                discord_client_mock.exchange_code.return_value = {
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
        self.disconnect_signals()
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
        set_primary_character(self.user, char)
        group, _ = Group.objects.get_or_create(name="Alliance")
        self.user.groups.add(group)

        with patch("discord.tasks.discord") as discord_mock:
            sync_discord_nickname(self.user, force_update=True)

            discord_mock.update_user.assert_called()

    @patch("discord.tasks.discord")
    @patch("discord.helpers.discord")
    def test_sync_discord_user(self, task_client, helper_client):
        self.disconnect_signals()

        helper_client.get_user.return_value = {
            "roles": ["Alliance", "Another"]
        }

        user = User.objects.create(id=1234)
        DiscordUser.objects.create(
            user=user,
            id=12345,
            discord_tag="XYZ",
        )
        group, _ = Group.objects.get_or_create(name="Alliance")
        DiscordRole.objects.create(
            role_id=1,
            name=group.name,
            group=group,
        )
        user.groups.add(group)

        sync_discord_user(user.id)

    def test_fake_login(self):
        User.objects.create(id=1234)
        mock_request = MagicMock()
        response = fake_login(mock_request, 1234)
        self.assertEqual(302, response.status_code)

    @patch("discord.helpers.discord")
    def test_remove_all_roles_from_guild_member_removes_roles(
        self, mock_discord
    ):
        # Simulate a user with roles
        mock_discord.get_user.return_value = {
            "nick": "TestNick",
            "roles": [1, 2, 3],
        }
        remove_all_roles_from_guild_member(12345)
        # Should call remove_user_role for each role
        assert mock_discord.remove_user_role.call_count == 3
        mock_discord.remove_user_role.assert_any_call(12345, 1)
        mock_discord.remove_user_role.assert_any_call(12345, 2)
        mock_discord.remove_user_role.assert_any_call(12345, 3)

    @patch("discord.helpers.discord")
    def test_remove_all_roles_from_guild_member_no_roles(self, mock_discord):
        # Simulate a user with no roles
        mock_discord.get_user.return_value = {"nick": "TestNick", "roles": []}
        remove_all_roles_from_guild_member(12345)
        # Should not call remove_user_role
        mock_discord.remove_user_role.assert_not_called()

    @patch("discord.helpers.discord")
    def test_remove_all_roles_from_guild_member_user_not_found(
        self, mock_discord
    ):
        # Simulate a 404 error from Discord API
        mock_response = MagicMock()
        mock_response.status_code = 404
        http_error = HTTPError(response=mock_response)
        mock_discord.get_user.side_effect = http_error
        # Should not raise, should just return
        remove_all_roles_from_guild_member(12345)
        mock_discord.remove_user_role.assert_not_called()


if __name__ == "__main__":
    unittest.main()
