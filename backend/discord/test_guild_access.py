"""Corporation Discord member policies: corporation or alliance members only."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone
from requests import HTTPError

from app.testing import make_token
from discord.guild_access import (
    AccessError,
    approve_held,
    enforce_guild,
    exempt_pending,
    normalize_username,
    save_member_policy,
)
from discord.guild_roles import KICK_MEMBERS, clear_role_mappings
from discord.models import (
    DiscordGuild,
    DiscordGuildExemption,
    DiscordGuildRemoval,
    DiscordUser,
)
from discord.test_guild_roles import GuildRoleFixture
from eveonline.constants import FL33T_MEMBER_ALLIANCE_IDS
from eveonline.models import EveCharacter

CLIENT = "discord.guild_access.DiscordClient"
BOT_ID = 5
OWNER_ID = 600
BOT_ROLE = 7001
STAFF_ROLE = 7002
HIGH_ROLE = 7003


def http_error(code: int) -> HTTPError:
    response = MagicMock(status_code=403)
    response.json.return_value = {"code": code}
    return HTTPError(response=response)


def person(discord_id, username, roles=(), bot=False):
    return {
        "user": {
            "id": str(discord_id),
            "username": username,
            "global_name": username.title(),
            "bot": bot,
        },
        "roles": [str(role_id) for role_id in roles],
    }


class GuildAccessFixture(GuildRoleFixture):
    def setUp(self):
        super().setUp()
        self.guild.can_kick_members = True
        self.guild.member_policy = DiscordGuild.MEMBER_POLICY_CORPORATION
        self.guild.save()
        # self.user flies in the corporation (the fixture's CEO).
        DiscordUser.objects.create(id=100, discord_tag="ceo", user=self.user)
        self.outsider = User.objects.create(username="outsider")
        EveCharacter.objects.create(
            character_id=3001,
            character_name="Outsider",
            user=self.outsider,
            corporation_id=1234,
            alliance_id=min(FL33T_MEMBER_ALLIANCE_IDS),
        )
        DiscordUser.objects.create(
            id=200, discord_tag="ally", user=self.outsider
        )
        self.roles = [
            {
                "id": str(self.guild.guild_id),
                "position": 0,
                "permissions": "0",
            },
            {"id": str(BOT_ROLE), "position": 5, "permissions": "0"},
            {
                "id": str(STAFF_ROLE),
                "position": 1,
                "permissions": str(KICK_MEMBERS),
            },
            {"id": str(HIGH_ROLE), "position": 9, "permissions": "0"},
        ]

    def discord(self, client_cls, members):
        client = client_cls.for_guild.return_value
        client.get_current_user.return_value = {"id": str(BOT_ID)}
        client.get_user.return_value = {"roles": [str(BOT_ROLE)]}
        client.get_roles.return_value = self.roles
        client.get_guild.return_value = {"owner_id": str(OWNER_ID)}
        client.get_members.return_value = [
            person(BOT_ID, "minmatarbot", [BOT_ROLE], bot=True),
            *members,
        ]
        return client

    def kicked(self, client):
        return {
            int(call.args[0])
            for call in client.kick_guild_member.call_args_list
        }

    def age_pending(self, hours=25):
        DiscordGuildRemoval.objects.update(
            flagged_at=timezone.now() - timedelta(hours=hours)
        )


class EnforceTestCase(GuildAccessFixture):
    @patch(CLIENT)
    def test_nobody_is_removed_before_the_grace_period(self, client_cls):
        client = self.discord(
            client_cls,
            [person(100, "ceo"), person(200, "ally"), person(300, "random")],
        )
        self.assertEqual(0, enforce_guild(self.guild))
        client.kick_guild_member.assert_not_called()
        reasons = dict(
            DiscordGuildRemoval.objects.values_list("discord_id", "reason")
        )
        self.assertEqual({200: "not_corporation", 300: "unlinked"}, reasons)

        self.age_pending()
        self.assertEqual(2, enforce_guild(self.guild))
        self.assertEqual({200, 300}, self.kicked(client))
        self.assertFalse(DiscordGuildRemoval.objects.exists())

    @patch(CLIENT)
    def test_alliance_policy_keeps_alliance_pilots(self, client_cls):
        self.guild.member_policy = DiscordGuild.MEMBER_POLICY_ALLIANCE
        self.guild.save()
        self.discord(
            client_cls,
            [person(100, "ceo"), person(200, "ally"), person(300, "random")],
        )
        enforce_guild(self.guild)
        reasons = dict(
            DiscordGuildRemoval.objects.values_list("discord_id", "reason")
        )
        self.assertEqual({300: "unlinked"}, reasons)

    @patch(CLIENT)
    def test_owner_staff_bots_and_higher_roles_are_never_flagged(
        self, client_cls
    ):
        self.discord(
            client_cls,
            [
                person(OWNER_ID, "owner"),
                person(301, "mod", [STAFF_ROLE]),
                person(302, "boss", [HIGH_ROLE]),
                person(303, "otherbot", bot=True),
            ],
        )
        enforce_guild(self.guild)
        self.assertFalse(DiscordGuildRemoval.objects.exists())

    @patch(CLIENT)
    def test_exempt_usernames_stay_and_follow_a_rename(self, client_cls):
        DiscordGuildExemption.objects.create(guild=self.guild, username="pal")
        self.discord(client_cls, [person(300, "pal")])
        enforce_guild(self.guild)
        self.assertFalse(DiscordGuildRemoval.objects.exists())
        exemption = DiscordGuildExemption.objects.get()
        self.assertEqual(300, exemption.discord_id)

        # Renamed: still exempt. Someone else taking "pal" is not.
        self.discord(
            client_cls, [person(300, "pal_renamed"), person(301, "pal")]
        )
        enforce_guild(self.guild)
        self.assertEqual(
            [301],
            list(
                DiscordGuildRemoval.objects.values_list(
                    "discord_id", flat=True
                )
            ),
        )

    @patch(CLIENT)
    def test_someone_who_qualifies_drops_off_the_list(self, client_cls):
        self.discord(client_cls, [person(200, "ally")])
        enforce_guild(self.guild)
        self.assertTrue(DiscordGuildRemoval.objects.exists())
        EveCharacter.objects.filter(user=self.outsider).update(
            corporation_id=98726134
        )
        self.age_pending()
        client = self.discord(client_cls, [person(200, "ally")])
        enforce_guild(self.guild)
        client.kick_guild_member.assert_not_called()
        self.assertFalse(DiscordGuildRemoval.objects.exists())

    @patch(CLIENT)
    def test_a_mass_removal_waits_for_approval(self, client_cls):
        members = [person(1000 + i, f"user{i}") for i in range(12)]
        client = self.discord(client_cls, [person(100, "ceo"), *members])
        enforce_guild(self.guild)
        self.age_pending()
        self.assertEqual(0, enforce_guild(self.guild))
        client.kick_guild_member.assert_not_called()
        self.guild.refresh_from_db()
        self.assertIsNotNone(self.guild.members_held_at)
        self.assertEqual(12, self.guild.members_held_count)

        with self.captureOnCommitCallbacks(execute=False):
            approve_held(self.guild)
        self.assertEqual(12, enforce_guild(self.guild))
        self.guild.refresh_from_db()
        self.assertIsNone(self.guild.members_held_at)
        self.assertIsNone(self.guild.members_approved_at)

    @patch(CLIENT)
    def test_repeated_missing_permissions_marks_kick_lost(self, client_cls):
        client = self.discord(
            client_cls, [person(300 + i, f"user{i}") for i in range(4)]
        )
        enforce_guild(self.guild)
        self.age_pending()
        client.kick_guild_member.side_effect = http_error(50013)
        self.assertEqual(0, enforce_guild(self.guild))
        self.assertEqual(3, client.kick_guild_member.call_count)
        self.guild.refresh_from_db()
        self.assertFalse(self.guild.can_kick_members)

    @patch(CLIENT)
    def test_protected_and_policy_free_servers_are_left_alone(
        self, client_cls
    ):
        self.guild.member_policy = ""
        self.guild.save()
        self.assertIsNone(enforce_guild(self.guild))
        self.guild.member_policy = "corporation"
        self.guild.is_primary = True
        self.guild.save()
        self.assertIsNone(enforce_guild(self.guild))
        client_cls.for_guild.assert_not_called()

    @patch(CLIENT)
    def test_an_empty_member_list_is_not_an_empty_server(self, client_cls):
        DiscordGuildRemoval.objects.create(
            guild=self.guild,
            discord_id=300,
            reason="unlinked",
            flagged_at=timezone.now() - timedelta(days=2),
        )
        client = self.discord(client_cls, [])
        client.get_members.return_value = []
        self.assertIsNone(enforce_guild(self.guild))
        client.kick_guild_member.assert_not_called()
        self.assertTrue(DiscordGuildRemoval.objects.exists())


class PolicySaveTestCase(GuildAccessFixture):
    def test_usernames_are_normalized_and_checked(self):
        self.assertEqual("bob.smith", normalize_username(" @Bob.Smith "))
        self.assertIsNone(normalize_username("has space"))
        with self.assertRaises(AccessError) as raised:
            save_member_policy(self.guild, "corporation", 24, ["no way"])
        self.assertEqual("invalid_username", raised.exception.code)

    def test_a_policy_needs_kick_members(self):
        self.guild.can_kick_members = False
        self.guild.save()
        with self.assertRaises(AccessError) as raised:
            save_member_policy(self.guild, "alliance", 24, [])
        self.assertEqual("cannot_kick_members", raised.exception.code)
        # Turning it off always works.
        save_member_policy(self.guild, "", 24, [])

    def test_changing_policy_restarts_the_grace_period(self):
        DiscordGuildRemoval.objects.create(
            guild=self.guild,
            discord_id=300,
            reason="unlinked",
            flagged_at=timezone.now() - timedelta(days=2),
        )
        with self.captureOnCommitCallbacks(execute=False):
            save_member_policy(self.guild, "alliance", 24, ["pal"])
        self.assertFalse(DiscordGuildRemoval.objects.exists())
        self.assertEqual(
            ["pal"],
            list(
                self.guild.member_exemptions.values_list("username", flat=True)
            ),
        )

    def test_keep_moves_a_pending_row_to_the_exemptions(self):
        DiscordGuildRemoval.objects.create(
            guild=self.guild,
            discord_id=300,
            username="pal",
            reason="unlinked",
            flagged_at=timezone.now(),
        )
        exempt_pending(self.guild, 300, self.user)
        exemption = DiscordGuildExemption.objects.get()
        self.assertEqual(
            ("pal", 300), (exemption.username, exemption.discord_id)
        )
        self.assertFalse(DiscordGuildRemoval.objects.exists())

    def test_releasing_the_server_clears_the_policy(self):
        DiscordGuildExemption.objects.create(guild=self.guild, username="pal")
        self.corporation.discord_guild = None
        self.corporation.save()
        clear_role_mappings(self.guild)
        self.guild.refresh_from_db()
        self.assertEqual("", self.guild.member_policy)
        self.assertFalse(self.guild.member_exemptions.exists())


class MemberEndpointTestCase(GuildAccessFixture):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.auth = {"HTTP_AUTHORIZATION": f"Bearer {make_token(self.user)}"}
        self.base = (
            "/api/eveonline/corporations/corporations/"
            f"{self.corporation.corporation_id}/discord/members"
        )

    @patch("discord.guild_access.queue_enforce")
    def test_a_director_saves_the_policy(self, queue_enforce):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.put(
                self.base,
                data={
                    "policy": "alliance",
                    "grace_hours": 72,
                    "exemptions": ["Pal", "@buddy"],
                },
                content_type="application/json",
                **self.auth,
            )
        self.assertEqual(200, response.status_code)
        access = response.json()["member_access"]
        self.assertEqual("alliance", access["policy"])
        self.assertEqual(72, access["grace_hours"])
        self.assertEqual(
            ["buddy", "pal"], [row["username"] for row in access["exemptions"]]
        )
        queue_enforce.assert_called_once_with(self.guild.pk)

        denied = self.client.put(
            self.base,
            data={"policy": None, "grace_hours": 24, "exemptions": []},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {make_token(self.outsider)}",
        )
        self.assertEqual(403, denied.status_code)

    def test_bad_grace_is_refused(self):
        response = self.client.put(
            self.base,
            data={"policy": "corporation", "grace_hours": 5},
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(400, response.status_code)
        self.assertEqual("invalid_grace", response.json()["detail"])

    def test_keep_and_approve(self):
        DiscordGuildRemoval.objects.create(
            guild=self.guild,
            discord_id=300,
            username="pal",
            reason="unlinked",
            flagged_at=timezone.now(),
        )
        response = self.client.post(
            f"{self.base}/exempt",
            data={"discord_id": "300"},
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual([], response.json()["member_access"]["pending"])

        refused = self.client.post(f"{self.base}/approve", **self.auth)
        self.assertEqual(400, refused.status_code)
        self.assertEqual("not_held", refused.json()["detail"])
