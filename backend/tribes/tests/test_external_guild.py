"""Tests for isolated tribe-group external Discord guild seats."""

from unittest.mock import MagicMock, patch

import requests
from django.contrib.auth.models import Group, User
from django.db.models import signals as django_signals
from django.test import TestCase, override_settings

from discord.models import DiscordGuild, DiscordUser
from discord.signals import group_post_save, user_group_changed
from tribes.helpers.external_guild import (
    append_query,
    build_pending_join_dm_message,
    decode_oauth_state,
    encode_oauth_state,
    join_seat_with_oauth_token,
    prepare_seats_for_user_delete,
    reconcile_external_guilds,
    send_pending_join_dm,
)
from tribes.models import (
    Tribe,
    TribeExternalGuild,
    TribeExternalGuildSeat,
    TribeGroup,
    TribeGroupMembership,
)
from users.helpers import offboard_user


def setUpModule():
    django_signals.post_save.disconnect(
        group_post_save,
        sender=Group,
        dispatch_uid="group_post_save",
    )
    django_signals.m2m_changed.disconnect(
        user_group_changed,
        sender=User.groups.through,
        dispatch_uid="user_group_changed",
    )


def _unknown_member_error() -> requests.exceptions.HTTPError:
    response = MagicMock()
    response.status_code = 404
    response.json.return_value = {"code": 10007}
    err = requests.exceptions.HTTPError("Unknown Member")
    err.response = response
    return err


class ExternalGuildSeatTestCase(TestCase):
    def setUp(self):
        self.guild = DiscordGuild.objects.create(
            guild_id=834087499658952735,
            name="Fishermen",
            is_primary=False,
            is_active=True,
        )
        self.tribe = Tribe.objects.create(name="Pulse", slug="pulse")
        self.tribe_group = TribeGroup.objects.create(
            tribe=self.tribe,
            name="Fishermen",
            code="pulse.fishermen",
        )
        self.binding = TribeExternalGuild.objects.create(
            tribe_group=self.tribe_group,
            guild=self.guild,
            member_role_id=111,
            alert_channel_id=1543302547157286972,
            is_active=True,
        )
        self.user = User.objects.create_user(username="pilot")
        self.discord_user = DiscordUser.objects.create(
            id=124039469488799746,
            discord_tag="bearthatcares#0",
            user=self.user,
            nickname="[A-RAT] BearThatCares",
        )

    @patch("tribes.helpers.external_guild.send_pending_join_dm")
    @patch("tribes.helpers.external_guild.client_for_binding")
    def test_active_membership_creates_pending_join_seat(
        self, client_for_binding, send_dm
    ):
        client = client_for_binding.return_value
        client.get_user.side_effect = _unknown_member_error()
        TribeGroupMembership.objects.create(
            user=self.user,
            tribe_group=self.tribe_group,
            status=TribeGroupMembership.STATUS_ACTIVE,
        )
        seat = TribeExternalGuildSeat.objects.get(binding=self.binding)
        self.assertEqual(seat.user_id, self.user.id)
        self.assertEqual(
            seat.status, TribeExternalGuildSeat.STATUS_PENDING_JOIN
        )
        send_dm.assert_called_once()

    @patch("tribes.helpers.external_guild.send_pending_join_dm")
    @patch("tribes.helpers.external_guild.client_for_binding")
    def test_active_membership_skips_dm_when_already_in_guild(
        self, client_for_binding, send_dm
    ):
        client = client_for_binding.return_value
        client.get_user.return_value = {
            "user": {"id": str(self.discord_user.id), "username": "bear"},
            "nick": "Bear",
            "roles": [],
        }
        TribeGroupMembership.objects.create(
            user=self.user,
            tribe_group=self.tribe_group,
            status=TribeGroupMembership.STATUS_ACTIVE,
        )
        seat = TribeExternalGuildSeat.objects.get(binding=self.binding)
        self.assertEqual(seat.status, TribeExternalGuildSeat.STATUS_PRESENT)
        send_dm.assert_not_called()

    @override_settings(
        DISCORD_EXTERNAL_GUILD_REDIRECT_URL=(
            "http://localhost:4321/redirects/external_guild_callback"
        ),
        DISCORD_CLIENT_ID="client-id",
        WEB_LINK_URL="https://my.minmatar.org",
    )
    @patch("tribes.helpers.external_guild.DiscordClient")
    def test_pending_join_dm_contains_oauth_link(self, discord_cls):
        seat = TribeExternalGuildSeat.objects.create(
            binding=self.binding,
            user=self.user,
            discord_user_id=self.discord_user.id,
            discord_username="bearthatcares",
            status=TribeExternalGuildSeat.STATUS_PENDING_JOIN,
        )
        message = build_pending_join_dm_message(seat)
        self.assertIn("Fishermen", message)
        self.assertIn("discord.com/api/oauth2/authorize", message)
        self.assertTrue(send_pending_join_dm(seat))
        discord_cls.return_value.send_dm.assert_called_once()

    @patch("tribes.helpers.external_guild.client_for_binding")
    def test_inactive_membership_kicks(self, client_for_binding):
        client = client_for_binding.return_value
        client.get_user.return_value = {
            "user": {"id": str(self.discord_user.id)},
            "roles": [],
        }
        TribeExternalGuildSeat.objects.create(
            binding=self.binding,
            user=self.user,
            discord_user_id=self.discord_user.id,
            discord_username="bearthatcares",
            status=TribeExternalGuildSeat.STATUS_PRESENT,
        )
        membership = TribeGroupMembership.objects.create(
            user=self.user,
            tribe_group=self.tribe_group,
            status=TribeGroupMembership.STATUS_ACTIVE,
        )
        membership.status = TribeGroupMembership.STATUS_INACTIVE
        membership.history_inactive_reason = "left"
        membership.save()

        seat = TribeExternalGuildSeat.objects.get(binding=self.binding)
        self.assertEqual(seat.status, TribeExternalGuildSeat.STATUS_REMOVED)
        client.kick_guild_member.assert_called()

    @patch("tribes.helpers.external_guild.client_for_binding")
    @patch("discord.signals.remove_all_roles_from_guild_member")
    def test_seat_survives_user_delete_with_username_snapshot(
        self, remove_roles_mock, client_for_binding
    ):
        del remove_roles_mock
        seat = TribeExternalGuildSeat.objects.create(
            binding=self.binding,
            user=self.user,
            discord_user_id=self.discord_user.id,
            discord_username="bearthatcares",
            discord_nickname="[A-RAT] BearThatCares",
            eve_name="BearThatCares",
            status=TribeExternalGuildSeat.STATUS_PRESENT,
        )
        offboard_user(self.user.id)
        seat.refresh_from_db()
        self.assertIsNone(seat.user_id)
        self.assertEqual(seat.discord_username, "bearthatcares")
        client_for_binding.return_value.kick_guild_member.assert_called()

    @patch("tribes.helpers.external_guild.client_for_binding")
    def test_reconciler_kicks_stray_role_holders(self, client_for_binding):
        client = client_for_binding.return_value
        client.get_members.return_value = [
            {
                "user": {"id": "999", "username": "stray", "bot": False},
                "roles": [str(self.binding.member_role_id)],
            },
            {
                "user": {"id": "1000", "username": "normal", "bot": False},
                "roles": [],
            },
        ]
        stats = reconcile_external_guilds()
        self.assertEqual(stats["kicked"], 1)
        client.kick_guild_member.assert_called_with(999)

    @patch("tribes.helpers.external_guild.client_for_binding")
    def test_oauth_join_targets_binding_guild_only(self, client_for_binding):
        client = client_for_binding.return_value
        seat = TribeExternalGuildSeat.objects.create(
            binding=self.binding,
            user=self.user,
            discord_user_id=self.discord_user.id,
            discord_username="bearthatcares",
            status=TribeExternalGuildSeat.STATUS_PENDING_JOIN,
        )
        client.get_user.return_value = {
            "user": {
                "id": str(self.discord_user.id),
                "username": "bearthatcares",
            },
            "nick": "Bear",
            "roles": [],
        }
        ok = join_seat_with_oauth_token(seat, "oauth-token")
        self.assertTrue(ok)
        client.add_guild_member.assert_called_once_with(
            self.discord_user.id, "oauth-token"
        )
        client.add_user_role.assert_called_once_with(
            self.discord_user.id, self.binding.member_role_id
        )
        seat.refresh_from_db()
        self.assertEqual(seat.status, TribeExternalGuildSeat.STATUS_PRESENT)

    @override_settings(WEB_LINK_URL="https://my.minmatar.org")
    def test_oauth_state_roundtrip(self):
        state = encode_oauth_state(
            group_id=19,
            user_id=92,
            redirect_url="https://my.minmatar.org/alliance/tribes/",
        )
        payload = decode_oauth_state(state)
        self.assertEqual(payload["group_id"], 19)
        self.assertEqual(payload["user_id"], 92)

    def test_append_query_without_second_question_mark(self):
        url = append_query(
            "http://localhost:4321/alliance/tribes/?tribe=pulse",
            external_guild="joined",
        )
        self.assertEqual(
            url,
            "http://localhost:4321/alliance/tribes/?tribe=pulse&external_guild=joined",
        )

    @patch("tribes.helpers.external_guild.client_for_binding")
    def test_prepare_seats_for_user_delete_direct(self, client_for_binding):
        seat = TribeExternalGuildSeat.objects.create(
            binding=self.binding,
            user=self.user,
            discord_user_id=self.discord_user.id,
            discord_username="bearthatcares",
            status=TribeExternalGuildSeat.STATUS_PRESENT,
        )
        prepare_seats_for_user_delete(self.user)
        seat.refresh_from_db()
        self.assertIsNone(seat.user_id)
        client_for_binding.return_value.kick_guild_member.assert_called_once()
