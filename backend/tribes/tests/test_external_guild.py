"""Tests for isolated tribe-group external Discord guild seats."""

from unittest.mock import MagicMock, patch

import requests
from django.contrib.auth.models import Group, User
from django.db.models import signals as django_signals
from django.test import TestCase, override_settings

from discord.models import DiscordGuild, DiscordUser
from discord.signals import group_post_save, user_group_changed
from eveonline.helpers.characters import set_primary_character
from eveonline.models import EveCharacter
from tribes.helpers.external_guild import (
    FISHERMEN_ALERT_CHANNEL_ID,
    FISHERMEN_MEMBER_ROLE_ID,
    append_query,
    apply_seat,
    build_pending_join_dm_message,
    decode_oauth_state,
    encode_oauth_state,
    expected_external_guild_nickname,
    join_seat_with_oauth_token,
    prepare_seats_for_user_delete,
    reconcile_external_guilds,
    seed_fishermen_external_guild,
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
        django_signals.post_save.disconnect(
            sender=EveCharacter,
            dispatch_uid="populate_eve_character_public_data",
        )
        django_signals.post_save.disconnect(
            sender=EveCharacter,
            dispatch_uid="populate_eve_character_private_data",
        )
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

    def _set_primary(self, name="Gray Vixen", character_id=2111111111):
        char = EveCharacter.objects.create(
            character_id=character_id,
            character_name=name,
            user=self.user,
        )
        set_primary_character(self.user, char)
        return char

    def test_expected_external_guild_nickname_format(self):
        self.assertEqual(
            expected_external_guild_nickname("Gray Vixen"),
            "[FL33T] Gray Vixen",
        )
        self.assertEqual(expected_external_guild_nickname(""), "")
        long_name = "A" * 40
        nick = expected_external_guild_nickname(long_name)
        self.assertTrue(nick.startswith("[FL33T] "))
        self.assertLessEqual(len(nick), 32)
        self.assertTrue(nick.endswith("…"))

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
        self._set_primary()
        TribeGroupMembership.objects.create(
            user=self.user,
            tribe_group=self.tribe_group,
            status=TribeGroupMembership.STATUS_ACTIVE,
        )
        seat = TribeExternalGuildSeat.objects.get(binding=self.binding)
        self.assertEqual(seat.status, TribeExternalGuildSeat.STATUS_PRESENT)
        send_dm.assert_not_called()
        client.update_user.assert_called_once_with(
            self.discord_user.id, "[FL33T] Gray Vixen"
        )
        self.assertEqual(seat.discord_nickname, "[FL33T] Gray Vixen")

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

    def test_active_membership_without_binding_creates_no_seat(self):
        self.binding.delete()
        TribeGroupMembership.objects.create(
            user=self.user,
            tribe_group=self.tribe_group,
            status=TribeGroupMembership.STATUS_ACTIVE,
        )
        self.assertFalse(TribeExternalGuildSeat.objects.exists())

    def test_seed_fishermen_external_guild_is_idempotent(self):
        existing_id = self.binding.pk
        binding = seed_fishermen_external_guild()
        self.assertEqual(binding.pk, existing_id)
        self.assertEqual(binding.member_role_id, 111)

    def test_seed_fishermen_external_guild_creates_missing_binding(self):
        self.binding.delete()
        binding = seed_fishermen_external_guild()
        self.assertIsNotNone(binding)
        self.assertEqual(binding.tribe_group_id, self.tribe_group.id)
        self.assertEqual(binding.member_role_id, FISHERMEN_MEMBER_ROLE_ID)
        self.assertEqual(binding.alert_channel_id, FISHERMEN_ALERT_CHANNEL_ID)
        self.assertTrue(binding.is_active)

    @patch("tribes.helpers.external_guild.send_pending_join_dm")
    @patch("tribes.helpers.external_guild.client_for_binding")
    def test_reconciler_backfills_seats_for_active_members(
        self, client_for_binding, send_dm
    ):
        self.binding.delete()
        TribeGroupMembership.objects.create(
            user=self.user,
            tribe_group=self.tribe_group,
            status=TribeGroupMembership.STATUS_ACTIVE,
        )
        self.assertFalse(TribeExternalGuildSeat.objects.exists())

        client = client_for_binding.return_value
        client.get_members.return_value = []
        client.get_user.side_effect = _unknown_member_error()
        stats = reconcile_external_guilds()

        self.assertEqual(stats["seats_ensured"], 1)
        seat = TribeExternalGuildSeat.objects.get()
        self.assertEqual(seat.user_id, self.user.id)
        self.assertEqual(
            seat.status, TribeExternalGuildSeat.STATUS_PENDING_JOIN
        )
        send_dm.assert_called_once()

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
        self._set_primary()
        ok = join_seat_with_oauth_token(seat, "oauth-token")
        self.assertTrue(ok)
        client.add_guild_member.assert_called_once_with(
            self.discord_user.id, "oauth-token"
        )
        client.add_user_role.assert_called_once_with(
            self.discord_user.id, self.binding.member_role_id
        )
        client.update_user.assert_called_once_with(
            self.discord_user.id, "[FL33T] Gray Vixen"
        )
        seat.refresh_from_db()
        self.assertEqual(seat.status, TribeExternalGuildSeat.STATUS_PRESENT)
        self.assertEqual(seat.discord_nickname, "[FL33T] Gray Vixen")

    @patch("tribes.helpers.external_guild.client_for_binding")
    def test_apply_seat_skips_nick_patch_when_already_expected(
        self, client_for_binding
    ):
        client = client_for_binding.return_value
        self._set_primary()
        seat = TribeExternalGuildSeat.objects.create(
            binding=self.binding,
            user=self.user,
            discord_user_id=self.discord_user.id,
            discord_username="bearthatcares",
            discord_nickname="old",
            eve_name="Gray Vixen",
            status=TribeExternalGuildSeat.STATUS_PRESENT,
        )
        client.get_user.return_value = {
            "user": {
                "id": str(self.discord_user.id),
                "username": "bearthatcares",
            },
            "nick": "[FL33T] Gray Vixen",
            "roles": [str(self.binding.member_role_id)],
        }
        apply_seat(seat, entitled=True)
        client.update_user.assert_not_called()
        seat.refresh_from_db()
        self.assertEqual(seat.discord_nickname, "[FL33T] Gray Vixen")

    @patch("tribes.helpers.external_guild.send_pending_join_dm")
    @patch("tribes.helpers.external_guild.client_for_binding")
    def test_reconciler_backfills_nicks_for_present_seats(
        self, client_for_binding, send_dm
    ):
        del send_dm
        client = client_for_binding.return_value
        self._set_primary()
        client.get_user.side_effect = _unknown_member_error()
        TribeGroupMembership.objects.create(
            user=self.user,
            tribe_group=self.tribe_group,
            status=TribeGroupMembership.STATUS_ACTIVE,
        )
        seat = TribeExternalGuildSeat.objects.get(binding=self.binding)
        self.assertEqual(
            seat.status, TribeExternalGuildSeat.STATUS_PENDING_JOIN
        )
        seat.status = TribeExternalGuildSeat.STATUS_PRESENT
        seat.discord_nickname = "[A-RAT] BearThatCares"
        seat.save(update_fields=["status", "discord_nickname", "updated_at"])
        client.get_user.side_effect = None
        client.get_user.return_value = {
            "user": {
                "id": str(self.discord_user.id),
                "username": "bearthatcares",
            },
            "nick": "[A-RAT] BearThatCares",
            "roles": [str(self.binding.member_role_id)],
        }
        client.get_members.return_value = [
            {
                "user": {
                    "id": str(self.discord_user.id),
                    "username": "bearthatcares",
                    "bot": False,
                },
                "nick": "[A-RAT] BearThatCares",
                "roles": [str(self.binding.member_role_id)],
            }
        ]
        client.update_user.reset_mock()
        stats = reconcile_external_guilds()
        self.assertGreaterEqual(stats["nicks_updated"], 1)
        client.update_user.assert_called_with(
            self.discord_user.id, "[FL33T] Gray Vixen"
        )
        seat.refresh_from_db()
        self.assertEqual(seat.discord_nickname, "[FL33T] Gray Vixen")

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
