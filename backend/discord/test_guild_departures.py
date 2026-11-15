"""Corporation servers: take every role off people who left."""

from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone

from app.testing import make_token
from discord.guild_departures import (
    StripError,
    approve_strip_hold,
    set_strip_on_leave,
    strip_guild,
)
from discord.guild_roles import clear_role_mappings
from discord.models import DiscordGuildExemption, DiscordUser
from discord.test_guild_access import (
    BOT_ROLE,
    HIGH_ROLE,
    OWNER_ID,
    STAFF_ROLE,
    GuildAccessFixture,
    http_error,
    person,
)
from eveonline.models import EveCharacter

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
        self.roles += [
            {"id": str(MANUAL_ROLE), "position": 2, "permissions": "0"},
            {
                "id": str(MANAGED_ROLE),
                "position": 3,
                "permissions": "0",
                "managed": True,
            },
            {"id": str(OTHER_ROLE), "position": 4, "permissions": "0"},
        ]
        self.leaver = self.linked(400, "leaver")

    def linked(self, discord_id, name, corporation_id=555, alliance_id=None):
        """A site user, linked on Discord, flying outside the alliance."""
        user = User.objects.create(username=name)
        EveCharacter.objects.create(
            character_id=10000 + discord_id,
            character_name=name.title(),
            user=user,
            corporation_id=corporation_id,
            alliance_id=alliance_id,
        )
        DiscordUser.objects.create(id=discord_id, discord_tag=name, user=user)
        return user

    def stripped(self, client):
        removed = {}
        for call in client.remove_user_role.call_args_list:
            removed.setdefault(int(call.args[0]), set()).add(int(call.args[1]))
        return removed


class StripTestCase(DepartureFixture):
    @patch(CLIENT)
    def test_only_people_who_left_lose_their_roles(self, client_cls):
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
        self.assertEqual(1, strip_guild(self.guild))
        # Never @everyone or a managed role.
        self.assertEqual(
            {400: {MANUAL_ROLE, OTHER_ROLE}}, self.stripped(client)
        )
        client.kick_guild_member.assert_not_called()
        self.guild.refresh_from_db()
        self.assertEqual(1, self.guild.roles_strip_last_count)
        self.assertIsNotNone(self.guild.roles_strip_checked_at)

    @patch(CLIENT)
    def test_someone_without_roles_is_left_alone(self, client_cls):
        client = self.discord(client_cls, [person(400, "leaver")])
        self.assertEqual(0, strip_guild(self.guild))
        client.remove_user_role.assert_not_called()

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
            ],
        )
        self.assertEqual(0, strip_guild(self.guild))
        client.remove_user_role.assert_not_called()

    @patch(CLIENT)
    def test_roles_at_or_above_the_bot_stay(self, client_cls):
        client = self.discord(
            client_cls, [person(400, "leaver", [BOT_ROLE, MANUAL_ROLE])]
        )
        # BOT_ROLE is the bot's top role, so the leaver is level with it.
        self.assertEqual(0, strip_guild(self.guild))
        client.remove_user_role.assert_not_called()

    @patch(CLIENT)
    def test_a_mass_strip_waits_for_approval(self, client_cls):
        leavers = [self.linked(1000 + i, f"user{i}") for i in range(12)]
        self.assertEqual(12, len(leavers))
        members = [
            person(1000 + i, f"user{i}", [MANUAL_ROLE]) for i in range(12)
        ]
        client = self.discord(client_cls, [person(100, "ceo"), *members])
        self.assertEqual(0, strip_guild(self.guild))
        client.remove_user_role.assert_not_called()
        self.guild.refresh_from_db()
        self.assertIsNotNone(self.guild.roles_strip_held_at)
        self.assertEqual(12, self.guild.roles_strip_held_count)

        with self.captureOnCommitCallbacks(execute=False):
            approve_strip_hold(self.guild)
        self.assertEqual(12, strip_guild(self.guild))
        self.guild.refresh_from_db()
        self.assertIsNone(self.guild.roles_strip_held_at)
        self.assertIsNone(self.guild.roles_strip_approved_at)

    def test_approving_needs_a_hold(self):
        with self.assertRaises(StripError) as raised:
            approve_strip_hold(self.guild)
        self.assertEqual("not_held", raised.exception.code)

    @patch(CLIENT)
    def test_losing_access_marks_the_server(self, client_cls):
        client = self.discord(
            client_cls, [person(400, "leaver", [MANUAL_ROLE])]
        )
        client.remove_user_role.side_effect = http_error(50001)
        self.assertIsNone(strip_guild(self.guild))
        self.guild.refresh_from_db()
        self.assertFalse(self.guild.can_manage_roles)

    @patch(CLIENT)
    def test_a_role_the_bot_cannot_touch_is_skipped(self, client_cls):
        client = self.discord(
            client_cls, [person(400, "leaver", [MANUAL_ROLE, OTHER_ROLE])]
        )
        client.remove_user_role.side_effect = [http_error(50013), None]
        self.assertEqual(1, strip_guild(self.guild))
        self.assertEqual(2, client.remove_user_role.call_count)

    @patch(CLIENT)
    def test_an_empty_member_list_is_not_an_empty_server(self, client_cls):
        client = self.discord(client_cls, [])
        client.get_members.return_value = []
        self.assertIsNone(strip_guild(self.guild))
        client.remove_user_role.assert_not_called()

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

    def test_turning_it_off_clears_a_hold(self):
        self.guild.strip_roles_on_leave = True
        self.guild.roles_strip_held_at = timezone.now()
        self.guild.roles_strip_held_count = 20
        self.guild.save()
        set_strip_on_leave(self.guild, False)
        self.guild.refresh_from_db()
        self.assertIsNone(self.guild.roles_strip_held_at)
        self.assertEqual(0, self.guild.roles_strip_held_count)

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
        self.corporation.discord_guild = None
        self.corporation.save()
        clear_role_mappings(self.guild)
        self.guild.refresh_from_db()
        self.assertFalse(self.guild.strip_roles_on_leave)
