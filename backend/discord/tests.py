import unittest
from unittest.mock import patch
from unittest.mock import Mock, MagicMock

from django.contrib.auth.models import User, Group
from django.test import SimpleTestCase
from django.db.models import signals

from eveonline.models import (
    EveCharacter,
    EvePrimaryCharacterChangeLog,
    EveCorporation,
)
from eveonline.helpers.characters import set_primary_character

from app.test import TestCase
from discord.core import make_nickname
from discord.models import DiscordUser, DiscordRole
from discord.views import discord_login_redirect, fake_login

from discord.tasks import sync_discord_nickname, sync_discord_user
from discord.helpers import remove_all_roles_from_guild_member


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

    @patch("discord.helpers.discord")
    def test_remove_all_roles_from_guild_member(self, discord_client_mock):
        """Test removing all roles from a Discord user on the guild."""
        # Case 1: DiscordUser exists in DB, should not remove roles
        DiscordUser.objects.create(id=111, user=self.user)
        discord_client_mock.get_user.return_value = {
            "nick": "TestNick",
            "roles": [1, 2, 3],
        }
        with patch("discord.models.DiscordUser.objects.filter") as filter_mock:
            filter_mock.return_value.first.return_value = DiscordUser(
                id=111, user=self.user
            )
            with patch.object(
                discord_client_mock, "remove_user_role"
            ) as remove_role_mock:
                remove_all_roles_from_guild_member(111)
                remove_role_mock.assert_not_called()

        # Case 2: DiscordUser does not exist, should remove all roles
        discord_client_mock.get_user.return_value = {
            "nick": "TestNick",
            "roles": [1, 2, 3],
        }
        with patch("discord.models.DiscordUser.objects.filter") as filter_mock:
            filter_mock.return_value.first.return_value = None
            with patch.object(
                discord_client_mock, "remove_user_role"
            ) as remove_role_mock:
                remove_all_roles_from_guild_member(111)
                remove_role_mock.assert_any_call(111, 1)
                remove_role_mock.assert_any_call(111, 2)
                remove_role_mock.assert_any_call(111, 3)
                self.assertEqual(remove_role_mock.call_count, 3)

        # Case 3: No roles to remove
        discord_client_mock.get_user.return_value = {
            "nick": "TestNick",
            "roles": [],
        }
        with patch("discord.models.DiscordUser.objects.filter") as filter_mock:
            filter_mock.return_value.first.return_value = None
            with patch.object(
                discord_client_mock, "remove_user_role"
            ) as remove_role_mock:
                remove_all_roles_from_guild_member(111)
                remove_role_mock.assert_not_called()

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
            sender=EvePrimaryCharacterChangeLog,
            dispatch_uid="notify_people_team_of_primary_character_change",
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
        mock_request = MagicMock()
        response = fake_login(mock_request)
        self.assertEqual(302, response.status_code)


if __name__ == "__main__":
    unittest.main()
