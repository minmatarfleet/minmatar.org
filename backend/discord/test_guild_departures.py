"""Corporation servers: take every role off people who left."""

from datetime import timedelta
from unittest.mock import patch

import requests
from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone

from app.testing import make_token
from discord.guild_departures import (
    APPROVAL_TTL,
    StripError,
    approve_strip_hold,
    set_strip_on_leave,
    strip_guild,
)
from discord.guild_roles import MANAGE_ROLES, clear_role_mappings
from discord.models import DiscordGuildExemption, DiscordRoleStrip, DiscordUser
from discord.test_guild_access import (
    BOT_ROLE,
    HIGH_ROLE,
    OWNER_ID,
    STAFF_ROLE,
    GuildAccessFixture,
    http_error,
    person,
)
from eveonline.models import EveCharacter, EveCharacterCorporationHistory

CLIENT = "discord.guild_departures.DiscordClient"
MANUAL_ROLE = 7004
MANAGED_ROLE = 7005
OTHER_ROLE = 7006


class DepartureFixture(GuildAccessFixture):
    def setUp(self):
        super().setUp()
        # Only the departures pass runs in these tests.
        self.guild.member_policy = ""
        self.guild.member_action = ""
        self.guild.strip_roles_on_leave = True
        self.guild.save()
        for role in self.roles:
            if role["id"] == str(BOT_ROLE):
                role["permissions"] = str(MANAGE_ROLES)
        self.roles += [
            {
                "id": str(MANUAL_ROLE),
                "name": "Manual",
                "position": 2,
                "permissions": "0",
            },
            {
                "id": str(MANAGED_ROLE),
                "name": "Booster",
                "position": 3,
                "permissions": "0",
                "managed": True,
            },
            {
                "id": str(OTHER_ROLE),
                "name": "Other",
                "position": 4,
                "permissions": "0",
            },
        ]
        self.leaver = self.linked(400, "leaver")

    def linked(self, discord_id, name, was_member=True, corporation_id=555):
        """A site user, linked on Discord, flying outside the alliance.
        was_member gives them a past stint in the server's corporation."""
        user = User.objects.create(username=name)
        character = EveCharacter.objects.create(
            character_id=10000 + discord_id,
            character_name=name.title(),
            user=user,
            corporation_id=corporation_id,
        )
        if was_member:
            EveCharacterCorporationHistory.objects.create(
                character=character,
                record_id=1,
                corporation_id=self.corporation.corporation_id,
                start_date=timezone.now() - timedelta(days=200),
            )
            EveCharacterCorporationHistory.objects.create(
                character=character,
                record_id=2,
                corporation_id=corporation_id,
                start_date=timezone.now() - timedelta(days=20),
            )
        DiscordUser.objects.create(id=discord_id, discord_tag=name, user=user)
        return user

    def kept(self, client):
        """discord id -> the roles the bot left them with."""
        return {
            int(call.args[0]): {int(role_id) for role_id in call.args[1]}
            for call in client.set_member_roles.call_args_list
        }

    def age_strips(self, hours=25):
        DiscordRoleStrip.objects.filter(stripped_at__isnull=True).update(
            flagged_at=timezone.now() - timedelta(hours=hours)
        )

    def pending_ids(self):
        return set(
            DiscordRoleStrip.objects.filter(
                stripped_at__isnull=True
            ).values_list("discord_id", flat=True)
        )

    def many_leavers(self, count):
        for i in range(count):
            self.linked(1000 + i, f"user{i}")
        return [
            person(1000 + i, f"user{i}", [MANUAL_ROLE]) for i in range(count)
        ]


class StripTestCase(DepartureFixture):
    @patch(CLIENT)
    def test_people_who_left_lose_their_roles_after_the_grace(
        self, client_cls
    ):
        everyone = self.guild.guild_id
        client = self.discord(
            client_cls,
            [
                # In the corporation.
                person(100, "ceo", [MANUAL_ROLE, OTHER_ROLE]),
                # Another corporation, still in the alliance.
                person(200, "ally", [MANUAL_ROLE]),
                # Not linked: we can't tell who this is.
                person(300, "random", [MANUAL_ROLE]),
                # Left the corporation and the alliance.
                person(
                    400,
                    "leaver",
                    [everyone, MANUAL_ROLE, MANAGED_ROLE, OTHER_ROLE],
                ),
            ],
        )
        # Flagged, not stripped: their corporation may not have caught up.
        self.assertEqual(0, strip_guild(self.guild))
        client.set_member_roles.assert_not_called()
        self.assertEqual({400}, self.pending_ids())

        self.age_strips()
        self.assertEqual(1, strip_guild(self.guild))
        # One request; @everyone and the managed role stay.
        self.assertEqual({400: {everyone, MANAGED_ROLE}}, self.kept(client))
        client.remove_user_role.assert_not_called()
        client.kick_guild_member.assert_not_called()
        row = DiscordRoleStrip.objects.get(discord_id=400)
        self.assertIsNotNone(row.stripped_at)
        self.assertEqual(
            [
                {"id": str(MANUAL_ROLE), "name": "Manual"},
                {"id": str(OTHER_ROLE), "name": "Other"},
            ],
            row.roles,
        )
        self.guild.refresh_from_db()
        self.assertEqual(1, self.guild.roles_strip_last_count)
        self.assertIsNotNone(self.guild.roles_strip_checked_at)

    @patch(CLIENT)
    def test_people_who_were_never_members_keep_their_roles(self, client_cls):
        # Signed in to apply: linked, but never in the corporation.
        self.linked(410, "applicant", was_member=False)
        client = self.discord(
            client_cls, [person(410, "applicant", [MANUAL_ROLE])]
        )
        self.assertEqual(0, strip_guild(self.guild))
        self.age_strips()
        self.assertEqual(0, strip_guild(self.guild))
        client.set_member_roles.assert_not_called()
        self.assertFalse(DiscordRoleStrip.objects.exists())

    @patch(CLIENT)
    def test_coming_back_in_the_grace_drops_them(self, client_cls):
        client = self.discord(
            client_cls, [person(400, "leaver", [MANUAL_ROLE])]
        )
        strip_guild(self.guild)
        self.assertEqual({400}, self.pending_ids())
        EveCharacter.objects.filter(user=self.leaver).update(
            corporation_id=self.corporation.corporation_id
        )
        self.age_strips()
        self.assertEqual(0, strip_guild(self.guild))
        client.set_member_roles.assert_not_called()
        self.assertEqual(set(), self.pending_ids())

    @patch(CLIENT)
    def test_someone_without_roles_is_left_alone(self, client_cls):
        client = self.discord(client_cls, [person(400, "leaver")])
        self.assertEqual(0, strip_guild(self.guild))
        client.set_member_roles.assert_not_called()
        self.assertFalse(DiscordRoleStrip.objects.exists())

    @patch(CLIENT)
    def test_owner_staff_exempt_and_higher_roles_keep_their_roles(
        self, client_cls
    ):
        self.linked(OWNER_ID, "owner")
        self.linked(301, "mod")
        self.linked(302, "boss")
        self.linked(304, "pal")
        DiscordGuildExemption.objects.create(guild=self.guild, username="pal")
        client = self.discord(
            client_cls,
            [
                person(OWNER_ID, "owner", [MANUAL_ROLE]),
                person(301, "mod", [STAFF_ROLE, MANUAL_ROLE]),
                person(302, "boss", [HIGH_ROLE, MANUAL_ROLE]),
                person(304, "pal", [MANUAL_ROLE]),
                # BOT_ROLE is the bot's top role: level with it.
                person(400, "leaver", [BOT_ROLE, MANUAL_ROLE]),
            ],
        )
        self.assertEqual(0, strip_guild(self.guild))
        client.set_member_roles.assert_not_called()
        self.assertFalse(DiscordRoleStrip.objects.exists())

    @patch(CLIENT)
    def test_a_mass_strip_waits_for_approval(self, client_cls):
        client = self.discord(
            client_cls, [person(100, "ceo"), *self.many_leavers(12)]
        )
        strip_guild(self.guild)
        self.age_strips()
        self.assertEqual(0, strip_guild(self.guild))
        client.set_member_roles.assert_not_called()
        self.guild.refresh_from_db()
        self.assertIsNotNone(self.guild.roles_strip_held_at)
        self.assertEqual(12, self.guild.roles_strip_held_count)

        with self.captureOnCommitCallbacks(execute=False):
            approve_strip_hold(self.guild)
        self.assertEqual(12, strip_guild(self.guild))
        self.guild.refresh_from_db()
        self.assertIsNone(self.guild.roles_strip_held_at)
        self.assertIsNone(self.guild.roles_strip_approved_at)

    @patch(CLIENT)
    def test_an_approval_covers_only_the_count_the_director_saw(
        self, client_cls
    ):
        members = self.many_leavers(15)
        client = self.discord(client_cls, [person(100, "ceo"), *members[:12]])
        strip_guild(self.guild)
        self.age_strips()
        strip_guild(self.guild)
        with self.captureOnCommitCallbacks(execute=False):
            approve_strip_hold(self.guild)

        # Three more turn up, flagged before the approval (a data problem).
        self.discord(client_cls, [person(100, "ceo"), *members])
        DiscordRoleStrip.objects.bulk_create(
            [
                DiscordRoleStrip(
                    guild=self.guild,
                    discord_id=1000 + i,
                    flagged_at=timezone.now() - timedelta(days=2),
                )
                for i in range(12, 15)
            ]
        )
        self.assertEqual(0, strip_guild(self.guild))
        client.set_member_roles.assert_not_called()
        self.guild.refresh_from_db()
        self.assertEqual(15, self.guild.roles_strip_held_count)
        self.assertIsNone(self.guild.roles_strip_approved_at)

    @patch(CLIENT)
    def test_an_unused_approval_expires(self, client_cls):
        client = self.discord(
            client_cls, [person(100, "ceo"), *self.many_leavers(12)]
        )
        strip_guild(self.guild)
        self.age_strips()
        strip_guild(self.guild)
        with self.captureOnCommitCallbacks(execute=False):
            approve_strip_hold(self.guild)
        self.guild.roles_strip_approved_at = (
            timezone.now() - APPROVAL_TTL - timedelta(minutes=1)
        )
        self.guild.save()
        self.assertEqual(0, strip_guild(self.guild))
        client.set_member_roles.assert_not_called()

    @patch(CLIENT)
    def test_a_pass_that_stops_early_keeps_the_approval(self, client_cls):
        client = self.discord(
            client_cls, [person(100, "ceo"), *self.many_leavers(12)]
        )
        strip_guild(self.guild)
        self.age_strips()
        strip_guild(self.guild)
        with self.captureOnCommitCallbacks(execute=False):
            approve_strip_hold(self.guild)
        client.set_member_roles.side_effect = [
            None,
            None,
            requests.Timeout("slow"),
        ]
        self.assertEqual(2, strip_guild(self.guild))
        self.guild.refresh_from_db()
        self.assertIsNotNone(self.guild.roles_strip_held_at)
        self.assertIsNotNone(self.guild.roles_strip_approved_at)
        self.assertEqual(10, len(self.pending_ids()))

        client.set_member_roles.side_effect = None
        self.assertEqual(10, strip_guild(self.guild))
        self.guild.refresh_from_db()
        self.assertIsNone(self.guild.roles_strip_approved_at)

    def test_approving_needs_a_hold(self):
        with self.assertRaises(StripError) as raised:
            approve_strip_hold(self.guild)
        self.assertEqual("not_held", raised.exception.code)

    @patch(CLIENT)
    def test_without_manage_roles_nothing_is_tried(self, client_cls):
        for role in self.roles:
            if role["id"] == str(BOT_ROLE):
                role["permissions"] = "0"
        client = self.discord(
            client_cls, [person(400, "leaver", [MANUAL_ROLE])]
        )
        self.assertIsNone(strip_guild(self.guild))
        client.set_member_roles.assert_not_called()
        self.guild.refresh_from_db()
        self.assertFalse(self.guild.can_manage_roles)

    @patch(CLIENT)
    def test_refusals_in_a_row_mean_the_permission_is_gone(self, client_cls):
        client = self.discord(
            client_cls, [person(100, "ceo"), *self.many_leavers(4)]
        )
        strip_guild(self.guild)
        self.age_strips()
        client.set_member_roles.side_effect = http_error(50013)
        self.assertIsNone(strip_guild(self.guild))
        self.assertEqual(3, client.set_member_roles.call_count)
        self.guild.refresh_from_db()
        self.assertFalse(self.guild.can_manage_roles)

    @patch(CLIENT)
    def test_one_refusal_is_skipped_and_retried(self, client_cls):
        client = self.discord(
            client_cls, [person(100, "ceo"), *self.many_leavers(2)]
        )
        strip_guild(self.guild)
        self.age_strips()
        client.set_member_roles.side_effect = [http_error(50013), None]
        self.assertEqual(1, strip_guild(self.guild))
        self.assertEqual(1, len(self.pending_ids()))
        self.guild.refresh_from_db()
        self.assertTrue(self.guild.can_manage_roles)

    @patch(CLIENT)
    def test_someone_who_left_the_server_is_dropped(self, client_cls):
        client = self.discord(
            client_cls, [person(400, "leaver", [MANUAL_ROLE])]
        )
        strip_guild(self.guild)
        self.age_strips()
        client.set_member_roles.side_effect = http_error(10007)
        self.assertEqual(0, strip_guild(self.guild))
        self.assertFalse(DiscordRoleStrip.objects.exists())

    @patch(CLIENT)
    def test_losing_access_marks_the_server(self, client_cls):
        client = self.discord(
            client_cls, [person(400, "leaver", [MANUAL_ROLE])]
        )
        strip_guild(self.guild)
        self.age_strips()
        client.set_member_roles.side_effect = http_error(50001)
        self.assertIsNone(strip_guild(self.guild))
        self.guild.refresh_from_db()
        self.assertFalse(self.guild.can_manage_roles)

    @patch(CLIENT)
    def test_an_empty_member_list_is_not_an_empty_server(self, client_cls):
        client = self.discord(client_cls, [])
        client.get_members.return_value = []
        self.assertIsNone(strip_guild(self.guild))
        client.set_member_roles.assert_not_called()

    @patch(CLIENT)
    def test_old_records_are_pruned(self, client_cls):
        self.discord(client_cls, [person(100, "ceo")])
        old = DiscordRoleStrip.objects.create(
            guild=self.guild,
            discord_id=999,
            flagged_at=timezone.now() - timedelta(days=100),
            stripped_at=timezone.now() - timedelta(days=95),
        )
        strip_guild(self.guild)
        self.assertFalse(DiscordRoleStrip.objects.filter(pk=old.pk).exists())

    @patch(CLIENT)
    def test_off_protected_and_unmanaged_servers_are_left_alone(
        self, client_cls
    ):
        self.guild.strip_roles_on_leave = False
        self.guild.save()
        self.assertIsNone(strip_guild(self.guild))
        self.guild.strip_roles_on_leave = True
        self.guild.is_primary = True
        self.guild.save()
        self.assertIsNone(strip_guild(self.guild))
        self.guild.is_primary = False
        self.guild.can_manage_roles = False
        self.guild.save()
        self.assertIsNone(strip_guild(self.guild))
        client_cls.for_guild.assert_not_called()

    @patch(CLIENT)
    def test_a_server_without_a_corporation_is_left_alone(self, client_cls):
        self.corporation.discord_guild = None
        self.corporation.save()
        self.assertIsNone(strip_guild(self.guild))
        client_cls.for_guild.assert_not_called()


class StripSettingTestCase(DepartureFixture):
    def setUp(self):
        super().setUp()
        self.guild.strip_roles_on_leave = False
        self.guild.roles_checked_at = timezone.now()
        self.guild.roles = [
            {
                "id": str(MANUAL_ROLE),
                "name": "Manual",
                "position": 2,
                "managed": False,
                "assignable": True,
            }
        ]
        self.guild.save()
        self.client = Client()
        self.auth = {"HTTP_AUTHORIZATION": f"Bearer {make_token(self.user)}"}
        self.base = (
            "/api/eveonline/corporations/corporations/"
            f"{self.corporation.corporation_id}/discord/roles"
        )

    def put(self, data, user=None):
        auth = self.auth
        if user is not None:
            auth = {"HTTP_AUTHORIZATION": f"Bearer {make_token(user)}"}
        return self.client.put(
            self.base, data=data, content_type="application/json", **auth
        )

    @patch("discord.guild_roles._queue_reconcile")
    @patch("discord.guild_departures.queue_strip")
    def test_a_director_turns_it_on_and_older_forms_keep_it(
        self, queue_strip, queue_reconcile
    ):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.put({"mappings": [], "strip_on_leave": True})
        self.assertEqual(200, response.status_code)
        self.assertTrue(response.json()["role_sync"]["strip_on_leave"])
        queue_strip.assert_called_once_with(self.guild.pk)

        # A page from before the option posts no flag: keep the setting.
        response = self.put({"mappings": []})
        self.assertEqual(200, response.status_code)
        self.assertTrue(response.json()["role_sync"]["strip_on_leave"])

        response = self.put({"mappings": [], "strip_on_leave": False})
        self.assertFalse(response.json()["role_sync"]["strip_on_leave"])

        denied = self.put(
            {"mappings": [], "strip_on_leave": True}, user=self.leaver
        )
        self.assertEqual(403, denied.status_code)
        self.assertTrue(queue_reconcile.called)

    def test_turning_it_off_clears_the_hold_and_who_is_waiting(self):
        self.guild.strip_roles_on_leave = True
        self.guild.roles_strip_held_at = timezone.now()
        self.guild.roles_strip_held_count = 20
        self.guild.save()
        DiscordRoleStrip.objects.create(
            guild=self.guild, discord_id=400, flagged_at=timezone.now()
        )
        done = DiscordRoleStrip.objects.create(
            guild=self.guild,
            discord_id=401,
            flagged_at=timezone.now(),
            stripped_at=timezone.now(),
        )
        set_strip_on_leave(self.guild, False)
        self.guild.refresh_from_db()
        self.assertIsNone(self.guild.roles_strip_held_at)
        self.assertEqual(0, self.guild.roles_strip_held_count)
        self.assertEqual(
            [done.pk],
            list(DiscordRoleStrip.objects.values_list("pk", flat=True)),
        )

    def test_settings_list_who_waits_and_what_was_removed(self):
        now = timezone.now()
        DiscordRoleStrip.objects.create(
            guild=self.guild,
            discord_id=400,
            username="leaver",
            flagged_at=now,
        )
        DiscordRoleStrip.objects.create(
            guild=self.guild,
            discord_id=401,
            username="gone",
            flagged_at=now - timedelta(days=2),
            stripped_at=now - timedelta(days=1),
            roles=[{"id": str(MANUAL_ROLE), "name": "Manual"}],
        )
        response = self.client.get(
            self.base.removesuffix("/roles"), **self.auth
        )
        self.assertEqual(200, response.status_code)
        role_sync = response.json()["role_sync"]
        self.assertEqual(1, role_sync["strip_pending_total"])
        self.assertEqual("400", role_sync["strip_pending"][0]["discord_id"])
        self.assertEqual(
            [{"id": str(MANUAL_ROLE), "name": "Manual"}],
            role_sync["strip_recent"][0]["roles"],
        )

    @patch("discord.guild_departures.queue_strip")
    def test_approve_endpoint(self, queue_strip):
        refused = self.client.post(f"{self.base}/strip/approve", **self.auth)
        self.assertEqual(400, refused.status_code)
        self.assertEqual("not_held", refused.json()["detail"])

        self.guild.roles_strip_held_at = timezone.now()
        self.guild.roles_strip_held_count = 20
        self.guild.save()
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                f"{self.base}/strip/approve", **self.auth
            )
        self.assertEqual(200, response.status_code)
        held = response.json()["role_sync"]["strip_held"]
        self.assertEqual(20, held["count"])
        self.assertTrue(held["approved"])
        queue_strip.assert_called_once_with(self.guild.pk)

    def test_releasing_the_server_turns_it_off(self):
        self.guild.strip_roles_on_leave = True
        self.guild.save()
        DiscordRoleStrip.objects.create(
            guild=self.guild, discord_id=400, flagged_at=timezone.now()
        )
        self.corporation.discord_guild = None
        self.corporation.save()
        clear_role_mappings(self.guild)
        self.guild.refresh_from_db()
        self.assertFalse(self.guild.strip_roles_on_leave)
        self.assertFalse(DiscordRoleStrip.objects.exists())
