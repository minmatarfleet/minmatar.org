import unittest
from unittest.mock import patch, Mock, MagicMock

from django.contrib.auth.models import User, Group
from django.test import SimpleTestCase, Client
from django.db.models import signals
from ratelimit import RateLimitException
from requests.exceptions import HTTPError

from eveonline.models import (
    EveCharacter,
    EveCorporation,
)
from eveonline.helpers.characters import set_primary_character

from app.test import TestCase
from discord.client import _raise_discord_rate_limit
from discord.core import DISCORD_NICKNAME_MAX_LENGTH, make_nickname
from discord.forms import DiscordChannelAdminForm
from discord.guilds import sync_discord_guilds
from discord.helpers import (
    get_discord_user,
    handle_discord_guild_member_error,
    is_discord_unknown_guild_member_error,
    remove_all_roles_from_guild_member,
    find_unregistered_guild_members,
)
from discord.models import (
    DiscordUser,
    DiscordRole,
    DiscordChannelActivityRecord,
    DiscordChannel,
    DiscordGuild,
)
from discord.signals import (
    group_post_save,
    resolve_existing_discord_role_from_server,
)
from discord.tasks import sync_discord_nickname, sync_discord_user
from discord.views import discord_login_redirect, fake_login


class DiscordSimpleTests(SimpleTestCase):
    """
    Unit tests for Discord functionality.
    """

    def test_basic_nickname(self):
        character = Mock(character_name="Bob", corporation_id=999)
        discord = Mock(is_down_under=False, dress_wearer=False)
        with patch("discord.core.EveCorporation") as eve_corp_model:
            eve_corp_model.objects.filter.return_value.first.return_value = (
                Mock(ticker="ABC")
            )
            self.assertEqual("[ABC] Bob", make_nickname(character, discord))

    def test_nickname_truncated_to_discord_limit(self):
        """Long character names are truncated to Discord's 32-char nickname limit."""
        long_name = "A" * 40
        character = Mock(character_name=long_name, corporation_id=999)
        discord = Mock(is_down_under=False, dress_wearer=False)
        with patch("discord.core.EveCorporation") as eve_corp_model:
            eve_corp_model.objects.filter.return_value.first.return_value = (
                Mock(ticker="L3ARN")
            )
            nickname = make_nickname(character, discord)
        self.assertLessEqual(
            len(nickname),
            DISCORD_NICKNAME_MAX_LENGTH,
            f"nickname length {len(nickname)} > {DISCORD_NICKNAME_MAX_LENGTH}",
        )
        self.assertTrue(nickname.startswith("[L3ARN] "))
        self.assertTrue(nickname.endswith("…"))


class DiscordRateLimitTests(SimpleTestCase):
    def test_raise_discord_rate_limit_uses_retry_after(self):
        response = MagicMock()
        response.headers = {"Retry-After": "2.5"}
        with self.assertRaises(RateLimitException) as ctx:
            _raise_discord_rate_limit(response)
        self.assertEqual(ctx.exception.period_remaining, 2.5)
        self.assertIn("rate limited", str(ctx.exception).lower())

    def test_raise_discord_rate_limit_defaults_when_header_invalid(self):
        response = MagicMock()
        response.headers = {"Retry-After": "soon"}
        with self.assertRaises(RateLimitException) as ctx:
            _raise_discord_rate_limit(response)
        self.assertEqual(ctx.exception.period_remaining, 1.0)

    def test_raise_discord_rate_limit_defaults_when_header_missing(self):
        response = MagicMock()
        response.headers = {}
        with self.assertRaises(RateLimitException) as ctx:
            _raise_discord_rate_limit(response)
        self.assertEqual(ctx.exception.period_remaining, 1.0)


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

    def test_user_group_change_signals_via_group_user_set(self):
        with patch("discord.signals.discord") as discord_mock:
            discord_mock.get_roles.return_value = []
            discord_mock.create_role.return_value.json.return_value = {
                "id": 2,
            }

            DiscordUser.objects.create(
                id=2,
                discord_tag="tag2",
                user=self.user,
            )
            group = Group.objects.create(name="reversegroup")

            group.user_set.add(self.user)

            discord_mock.get_roles.assert_called()
            discord_mock.create_role.assert_called_with("reversegroup")

    @patch("discord.signals.discord")
    def test_group_post_save_relinks_existing_role_id(self, discord_mock):
        """HF: recreating a group with an existing Discord role_id must not IntegrityError."""
        discord_mock.get_roles.return_value = [
            {"id": 1486197729745965067, "name": "Tribe - Chief"},
        ]
        signals.post_save.disconnect(
            sender=Group, dispatch_uid="group_post_save"
        )
        signals.pre_save.disconnect(
            sender=DiscordRole,
            dispatch_uid="resolve_existing_discord_role_from_server",
        )
        old_group = Group.objects.create(name="Old Chief Group")
        DiscordRole.objects.create(
            role_id=1486197729745965067,
            name="Tribe - Chief",
            group=old_group,
        )
        signals.pre_save.connect(
            resolve_existing_discord_role_from_server,
            sender=DiscordRole,
            dispatch_uid="resolve_existing_discord_role_from_server",
        )
        signals.post_save.connect(
            group_post_save,
            sender=Group,
            dispatch_uid="group_post_save",
        )

        new_group = Group.objects.create(name="Tribe - Chief")

        role = DiscordRole.objects.get(role_id=1486197729745965067)
        self.assertEqual(role.group_id, new_group.id)
        self.assertEqual(role.name, "Tribe - Chief")
        self.assertEqual(
            DiscordRole.objects.filter(role_id=1486197729745965067).count(),
            1,
        )
        discord_mock.create_role.assert_not_called()


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
            corporation_id=corp.corporation_id,
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

    def test_handle_discord_guild_member_error_unknown_member(self):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.json.return_value = {
            "message": "Unknown Member",
            "code": 10007,
        }
        exc = HTTPError(response=mock_response)
        self.assertTrue(is_discord_unknown_guild_member_error(exc))

    def test_bare_404_is_not_unknown_member(self):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.json.side_effect = ValueError("not json")
        exc = HTTPError(response=mock_response)
        self.assertFalse(is_discord_unknown_guild_member_error(exc))

    @patch("discord.helpers.offboard_user")
    def test_handle_discord_guild_member_error_offboards_user(
        self, mock_offboard
    ):
        DiscordUser.objects.create(id=999, user=self.user, discord_tag="x")
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.json.return_value = {
            "message": "Unknown Member",
            "code": 10007,
        }
        exc = HTTPError(response=mock_response)
        self.assertTrue(
            handle_discord_guild_member_error(self.user, exc, "test_context")
        )
        mock_offboard.assert_called_once_with(self.user.id)

    @patch("discord.helpers.offboard_user")
    def test_handle_discord_guild_member_error_does_not_offboard_bare_404(
        self, mock_offboard
    ):
        DiscordUser.objects.create(id=998, user=self.user, discord_tag="x")
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.json.side_effect = ValueError("not json")
        exc = HTTPError(response=mock_response)
        self.assertFalse(
            handle_discord_guild_member_error(self.user, exc, "test_context")
        )
        mock_offboard.assert_not_called()


class VoiceTrackingRouterTestCase(TestCase):
    """Test cases for Discord voice tracking ingestion."""

    def setUp(self):
        self.client = Client()
        super().setUp()
        self.guild, _ = DiscordGuild.objects.get_or_create(
            guild_id=1041384161505722368,
            defaults={
                "name": "Minmatar",
                "is_primary": True,
                "is_active": True,
            },
        )
        self.channel = DiscordChannel.objects.create(
            guild=self.guild,
            channel_id=1306515072650313728,
            name="Fleet 1",
            channel_type=DiscordChannel.VOICE,
            track_voice_activity=True,
        )

    def test_get_tracked_voice_channels(self):
        DiscordChannel.objects.create(
            guild=self.guild,
            channel_id=999,
            name="AFK",
            channel_type=DiscordChannel.VOICE,
            track_voice_activity=False,
        )

        response = self.client.get(
            "/api/discord/voicetracking/channels",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(200, response.status_code)
        channels = response.json()["channels"]
        self.assertEqual(1, len(channels))
        self.assertEqual(1306515072650313728, channels[0]["channel_id"])
        self.assertEqual("Fleet 1", channels[0]["name"])

    def test_create_voice_tracking_records(self):
        data = {
            "minutes": 7,
            "channel_id": self.channel.channel_id,
            "channel_name": self.channel.name,
            "usernames": [self.user.username],
        }

        response = self.client.post(
            "/api/discord/voicetracking/records",
            data,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(200, response.status_code)
        ids = response.json()["ids"]
        self.assertEqual(1, len(ids))

        record = DiscordChannelActivityRecord.objects.get(id=ids[0])
        self.assertEqual(
            DiscordChannelActivityRecord.VOICE_MINUTE, record.activity_type
        )
        self.assertEqual(7, record.quantity)
        self.assertEqual(self.channel.channel_id, record.channel_id)
        self.assertEqual("Fleet 1", record.channel_name)

    def test_create_activity_records(self):
        data = {
            "activity_type": DiscordChannelActivityRecord.VOICE_MINUTE,
            "quantity": 3,
            "channel_id": self.channel.channel_id,
            "channel_name": self.channel.name,
            "usernames": [self.user.username],
        }

        response = self.client.post(
            "/api/discord/activity/records",
            data,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(200, response.status_code)
        record = DiscordChannelActivityRecord.objects.get(
            id=response.json()["ids"][0]
        )
        self.assertEqual(
            DiscordChannelActivityRecord.VOICE_MINUTE, record.activity_type
        )
        self.assertEqual(3, record.quantity)

    def test_create_voice_tracking_records_ignores_untracked_channel(self):
        data = {
            "minutes": 7,
            "channel_id": 123456789,
            "channel_name": "Untracked",
            "usernames": [self.user.username],
        }

        response = self.client.post(
            "/api/discord/voicetracking/records",
            data,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(200, response.status_code)
        self.assertEqual([], response.json()["ids"])
        self.assertEqual(0, DiscordChannelActivityRecord.objects.count())


class DiscordGuildSyncTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        super().setUp()

    @patch("discord.guilds.discord.get_bot_guilds")
    def test_sync_discord_guilds_from_api(self, mock_get_bot_guilds):
        mock_get_bot_guilds.return_value = [
            {"id": 1041384161505722368, "name": "Minmatar"},
            {"id": 999, "name": "Other Server"},
        ]

        synced = sync_discord_guilds()

        self.assertEqual(2, synced)
        self.assertTrue(
            DiscordGuild.objects.get(guild_id=1041384161505722368).is_primary
        )
        self.assertTrue(DiscordGuild.objects.get(guild_id=999).is_active)

        mock_get_bot_guilds.return_value = [
            {"id": 1041384161505722368, "name": "Minmatar"},
        ]
        sync_discord_guilds()
        self.assertFalse(DiscordGuild.objects.get(guild_id=999).is_active)

    def test_sync_guilds_from_bot_endpoint(self):
        response = self.client.post(
            "/api/discord/guilds/sync",
            {
                "guilds": [
                    {"id": 1041384161505722368, "name": "Minmatar"},
                ]
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(200, response.status_code)
        self.assertEqual(1, response.json()["synced"])
        guild = DiscordGuild.objects.get(guild_id=1041384161505722368)
        self.assertEqual("Minmatar", guild.name)
        self.assertTrue(guild.is_active)


class DiscordChannelAdminFormTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.guild = DiscordGuild.objects.create(
            guild_id=999888777,
            name="Test Guild",
            is_active=True,
        )

    @patch("discord.forms.fetch_active_guild_channels")
    @patch("discord.forms.get_guild_channel")
    def test_track_voice_activity_rejected_for_text_channel(
        self, mock_get_channel, mock_fetch_active
    ):
        mock_fetch_active.return_value = [
            {
                "id": 123,
                "name": "general",
                "type": "text",
                "guild_id": self.guild.guild_id,
            },
        ]
        mock_get_channel.return_value = mock_fetch_active.return_value[0]
        form = DiscordChannelAdminForm(
            data={
                "discord_channel_pick": "123",
                "track_voice_activity": True,
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("track_voice_activity", form.errors)

    @patch("discord.forms.fetch_active_guild_channels")
    @patch("discord.forms.get_guild_channel")
    def test_receive_capital_pings_rejected_for_voice_channel(
        self, mock_get_channel, mock_fetch_active
    ):
        mock_fetch_active.return_value = [
            {
                "id": 456,
                "name": "comms",
                "type": "voice",
                "guild_id": self.guild.guild_id,
            },
        ]
        mock_get_channel.return_value = mock_fetch_active.return_value[0]
        form = DiscordChannelAdminForm(
            data={
                "discord_channel_pick": "456",
                "track_voice_activity": False,
                "receive_capital_pings": True,
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("receive_capital_pings", form.errors)

    @patch("discord.forms.fetch_active_guild_channels")
    @patch("discord.forms.get_guild_channel")
    def test_receive_amarr_fleet_pings_rejected_for_voice_channel(
        self, mock_get_channel, mock_fetch_active
    ):
        mock_fetch_active.return_value = [
            {
                "id": 456,
                "name": "comms",
                "type": "voice",
                "guild_id": self.guild.guild_id,
            },
        ]
        mock_get_channel.return_value = mock_fetch_active.return_value[0]
        form = DiscordChannelAdminForm(
            data={
                "discord_channel_pick": "456",
                "track_voice_activity": False,
                "receive_amarr_fleet_pings": True,
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("receive_amarr_fleet_pings", form.errors)


class DiscordOffboardSyncTests(TestCase):
    """A5/MG: offboard during sync must not 500, and message must be correct."""

    def _unknown_member_error(self):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.json.return_value = {
            "message": "Unknown Member",
            "code": 10007,
        }
        return HTTPError(response=mock_response)

    @patch("discord.helpers.discord")
    @patch("discord.helpers.offboard_user")
    def test_get_discord_user_posts_offboard_message_when_notify(
        self, mock_offboard, mock_discord
    ):
        DiscordUser.objects.create(id=999, user=self.user, discord_tag="x")
        mock_discord.get_user.side_effect = self._unknown_member_error()

        result = get_discord_user(self.user, notify=True)

        self.assertIsNone(result)
        mock_offboard.assert_called_once_with(self.user.id)
        message = mock_discord.create_message.call_args[0][1]
        self.assertIn("offboarded", message)
        self.assertNotIn("Ushra'Khant", message)

    @patch("discord.helpers.discord")
    @patch("discord.helpers.offboard_user")
    def test_get_discord_user_skips_message_when_notify_false(
        self, mock_offboard, mock_discord
    ):
        DiscordUser.objects.create(id=998, user=self.user, discord_tag="x")
        mock_discord.get_user.side_effect = self._unknown_member_error()

        result = get_discord_user(self.user, notify=False)

        self.assertIsNone(result)
        mock_offboard.assert_called_once_with(self.user.id)
        mock_discord.create_message.assert_not_called()

    def test_sync_discord_nickname_missing_user_is_noop(self):
        sync_discord_nickname(999999, force_update=True)

    def test_sync_discord_user_missing_user_is_noop(self):
        sync_discord_user(999999)

    @patch("users.router.sync_discord_user")
    @patch("users.router.update_affiliation")
    def test_sync_user_endpoint_returns_410_after_offboard(
        self, mock_affiliation, mock_sync
    ):
        user_id = self.user.id

        def delete_user(synced_user_id):
            User.objects.filter(id=synced_user_id).delete()

        mock_sync.side_effect = delete_user
        client = Client()
        response = client.post(
            f"/api/users/{user_id}/sync",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 410)
        self.assertIn(b"offboarded", response.content)

    @patch("users.router.sync_discord_user")
    @patch("users.router.update_affiliation")
    def test_sync_user_endpoint_returns_404_when_user_missing(
        self, mock_affiliation, mock_sync
    ):
        mock_affiliation.side_effect = User.DoesNotExist
        client = Client()
        response = client.post(
            f"/api/users/{self.user.id}/sync",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 404)
        self.assertIn(b"not found", response.content)
        mock_sync.assert_not_called()


if __name__ == "__main__":
    unittest.main()
