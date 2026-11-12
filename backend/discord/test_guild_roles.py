"""Corporation and tribe Discord role mappings.

The reconciler adds and removes mapped roles for linked accounts. It does
not kick, and it does not touch the alliance Discord or a Fishermen server.
"""

from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.db.models import signals
from django.test import Client
from django.utils import timezone
from requests import HTTPError

from app.test import TestCase
from app.testing import make_token
from discord.channels import admin_picker_guilds
from discord.guild_roles import (
    CORPORATION_STATES,
    TRIBE_STATES,
    MappingError,
    install_block_reason,
    qualifying_user_ids,
    reconcile_guild_role_mappings,
    replace_role_mappings,
    snapshot_guild_roles,
)
from discord.models import DiscordGuild, DiscordRoleMapping, DiscordUser
from eveonline.constants import FL33T_MEMBER_ALLIANCE_IDS
from eveonline.models import EveCharacter, EveCorporation
from groups.helpers import CORPORATION_GROUP_SUFFIXES
from groups.models import EveCorporationGroup
from tribes.models import (
    Tribe,
    TribeExternalGuild,
    TribeGroup,
    TribeGroupMembership,
)

CLIENT = "discord.guild_roles.DiscordClient"
ROLE_MEMBER = 9001
ROLE_DIRECTOR = 9002
ROLE_OTHER = 9003


def http_error(code: int) -> HTTPError:
    response = MagicMock(status_code=403)
    response.json.return_value = {"code": code}
    return HTTPError(response=response)


def member(discord_id, roles, bot=False):
    return {
        "user": {"id": str(discord_id), "bot": bot},
        "roles": [str(role_id) for role_id in roles],
    }


class GuildRoleFixture(TestCase):
    def setUp(self):
        super().setUp()
        for uid in (
            "populate_eve_character_public_data",
            "populate_eve_character_private_data",
        ):
            signals.post_save.disconnect(sender=EveCharacter, dispatch_uid=uid)
        signals.post_save.disconnect(
            sender=TribeGroupMembership,
            dispatch_uid="tribe_group_membership_post_save",
        )
        self.guild = DiscordGuild.objects.create(
            guild_id=4242,
            name="Rattini",
            is_active=True,
            can_manage_roles=True,
        )
        self.ceo = EveCharacter.objects.create(
            character_id=2001,
            character_name="Ceo",
            user=self.user,
            corporation_id=98726134,
        )
        self.corporation = EveCorporation.objects.create(
            corporation_id=98726134,
            name="Rattini Tribe",
            ceo=self.ceo,
            discord_guild=self.guild,
        )
        self.corporation.discord_bot_status = "ok"
        self.corporation.save()

    def map(self, state, role_id):
        return DiscordRoleMapping.objects.create(
            guild=self.guild, state=state, role_id=role_id
        )


class QualifyingUsersTestCase(GuildRoleFixture):
    def test_corporation_states_use_stored_sets(self):
        director = EveCharacter.objects.create(
            character_id=2002,
            character_name="Dir",
            user=User.objects.create(username="dir"),
            corporation_id=self.corporation.corporation_id,
        )
        recruiter = EveCharacter.objects.create(
            character_id=2003,
            character_name="Rec",
            user=User.objects.create(username="rec"),
            corporation_id=1,
        )
        steward = EveCharacter.objects.create(
            character_id=2004,
            character_name="Struct",
            user=User.objects.create(username="struct"),
            corporation_id=1,
        )
        alliance = EveCharacter.objects.create(
            character_id=2005,
            character_name="Ally",
            user=User.objects.create(username="ally"),
            corporation_id=1,
            alliance_id=next(iter(FL33T_MEMBER_ALLIANCE_IDS)),
        )
        outsider = EveCharacter.objects.create(
            character_id=2006,
            character_name="Out",
            user=User.objects.create(username="out"),
            corporation_id=1,
            alliance_id=1,
        )
        self.corporation.directors.add(director)
        self.corporation.recruiters.add(recruiter)
        self.corporation.stewards.add(steward)

        qualified = qualifying_user_ids(
            "corporation", self.corporation, set(CORPORATION_STATES)
        )
        self.assertIn(self.user.id, qualified["member"])
        self.assertIn(director.user_id, qualified["member"])
        self.assertNotIn(outsider.user_id, qualified["member"])
        self.assertEqual({director.user_id}, qualified["director"])
        self.assertEqual({recruiter.user_id}, qualified["recruiter"])
        self.assertEqual({steward.user_id}, qualified["structure_manager"])
        self.assertIn(alliance.user_id, qualified["alliance_member"])
        self.assertNotIn(outsider.user_id, qualified["alliance_member"])

    def test_tribe_member_is_an_active_group_membership(self):
        tribe = Tribe.objects.create(name="Pulse", slug="pulse-q")
        tribe.discord_guild = self.guild
        tribe.save()
        self.corporation.discord_guild = None
        self.corporation.discord_bot_status = ""
        self.corporation.save()
        group = TribeGroup.objects.create(
            tribe=tribe, name="Miners", code="pulse.miners-q"
        )
        active = User.objects.create(username="active")
        pending = User.objects.create(username="pending")
        TribeGroupMembership.objects.create(
            user=active,
            tribe_group=group,
            status=TribeGroupMembership.STATUS_ACTIVE,
        )
        TribeGroupMembership.objects.create(
            user=pending,
            tribe_group=group,
            status=TribeGroupMembership.STATUS_PENDING,
        )
        qualified = qualifying_user_ids("tribe", tribe, set(TRIBE_STATES))
        self.assertEqual({active.id}, qualified["member"])
        self.assertNotIn("director", qualified)

    def test_structure_manager_does_not_rename_the_alliance_role(self):
        self.assertIn(" Gunner", CORPORATION_GROUP_SUFFIXES.values())
        self.assertEqual("gunner", EveCorporationGroup.GROUP_TYPE_GUNNER)
        self.assertTrue(hasattr(EveCorporation, "stewards"))


class ReconcileRolesTestCase(GuildRoleFixture):
    def setUp(self):
        super().setUp()
        self.map("member", ROLE_MEMBER)
        self.map("director", ROLE_DIRECTOR)
        self.discord_user = DiscordUser.objects.create(
            id=555, discord_tag="pilot", user=self.user
        )

    @patch(CLIENT)
    def test_linked_member_gains_and_loses_only_mapped_roles(self, client_cls):
        client = client_cls.for_guild.return_value
        stranger = 777
        client.get_members.return_value = [
            member(555, [ROLE_DIRECTOR, ROLE_OTHER]),
            member(stranger, [ROLE_MEMBER]),
            member(1, [ROLE_MEMBER], bot=True),
        ]
        reconcile_guild_role_mappings(self.guild.pk)
        client_cls.assert_not_called()
        client_cls.for_guild.assert_called_once_with(4242)
        client.add_user_role.assert_called_once_with(555, ROLE_MEMBER)
        client.remove_user_role.assert_called_once_with(555, ROLE_DIRECTOR)
        client.kick_guild_member.assert_not_called()
        client.leave_guild.assert_not_called()

    @patch(CLIENT)
    def test_primary_and_fishermen_guilds_are_not_synced(self, client_cls):
        self.guild.is_primary = True
        self.guild.save()
        reconcile_guild_role_mappings(self.guild.pk)
        client_cls.for_guild.assert_not_called()

        self.guild.is_primary = False
        self.guild.save()
        group = TribeGroup.objects.create(
            tribe=Tribe.objects.create(name="Pulse", slug="pulse-f"),
            name="Fishermen",
            code="pulse.fishermen-f",
        )
        TribeExternalGuild.objects.create(
            tribe_group=group, guild=self.guild, member_role_id=1
        )
        reconcile_guild_role_mappings(self.guild.pk)
        client_cls.for_guild.assert_not_called()

    @patch(CLIENT)
    def test_missing_permission_stops_the_guild(self, client_cls):
        client = client_cls.for_guild.return_value
        client.get_members.side_effect = http_error(50013)
        reconcile_guild_role_mappings(self.guild.pk)
        self.guild.refresh_from_db()
        self.assertFalse(self.guild.can_manage_roles)
        self.assertIsNotNone(self.guild.roles_checked_at)
        client.add_user_role.assert_not_called()


class InstallBlockTestCase(GuildRoleFixture):
    def test_refuses_before_a_code_would_be_exchanged(self):
        self.assertEqual("missing_guild", install_block_reason(None))
        self.assertEqual("missing_guild", install_block_reason("nope"))
        with self.settings(DISCORD_GUILD_ID=4242):
            self.assertEqual(
                "alliance_server",
                install_block_reason(
                    4242, corporation_id=self.corporation.corporation_id
                ),
            )
        self.guild.is_primary = True
        self.guild.save()
        self.assertEqual("alliance_server", install_block_reason(4242))

    def test_refuses_a_server_someone_else_owns(self):
        other = EveCorporation.objects.create(corporation_id=42, name="Other")
        self.assertEqual(
            "guild_taken",
            install_block_reason(4242, corporation_id=other.corporation_id),
        )
        self.assertIsNone(
            install_block_reason(
                4242, corporation_id=self.corporation.corporation_id
            )
        )
        self.corporation.discord_guild = None
        self.corporation.save()
        tribe = Tribe.objects.create(
            name="Caps", slug="caps", discord_guild=self.guild
        )
        self.assertEqual(
            "guild_taken", install_block_reason(4242, tribe_id=tribe.pk + 1)
        )
        self.assertIsNone(install_block_reason(4242, tribe_id=tribe.pk))

    def test_fishermen_is_an_alliance_server_for_installs(self):
        group = TribeGroup.objects.create(
            tribe=Tribe.objects.create(name="Pulse", slug="pulse-b"),
            name="Fishermen",
            code="pulse.fishermen-b",
        )
        TribeExternalGuild.objects.create(
            tribe_group=group, guild=self.guild, member_role_id=1
        )
        self.assertEqual("alliance_server", install_block_reason(4242))


class MappingSaveTestCase(GuildRoleFixture):
    def setUp(self):
        super().setUp()
        self.guild.roles = [
            {"id": str(ROLE_MEMBER), "name": "Members", "assignable": True},
            {
                "id": str(ROLE_DIRECTOR),
                "name": "Directors",
                "assignable": True,
            },
        ]
        self.guild.roles_checked_at = timezone.now()
        self.guild.save()

    def test_a_role_cannot_be_saved_twice(self):
        with self.assertRaises(MappingError) as raised:
            replace_role_mappings(
                self.guild,
                [
                    {"state": "member", "role_id": str(ROLE_MEMBER)},
                    {"state": "director", "role_id": str(ROLE_MEMBER)},
                ],
                set(CORPORATION_STATES),
            )
        self.assertEqual("duplicate_role", raised.exception.code)

    def test_a_tribe_cannot_map_a_corporation_office(self):
        with self.assertRaises(MappingError) as raised:
            replace_role_mappings(
                self.guild,
                [{"state": "director", "role_id": str(ROLE_DIRECTOR)}],
                set(TRIBE_STATES),
            )
        self.assertEqual("state_not_allowed", raised.exception.code)

    def test_clearing_a_state_drops_its_row(self):
        self.map("member", ROLE_MEMBER)
        with self.captureOnCommitCallbacks(execute=False):
            replace_role_mappings(
                self.guild,
                [{"state": "member", "role_id": None}],
                set(CORPORATION_STATES),
            )
        self.assertFalse(self.guild.role_mappings.exists())


class SnapshotAndPickerTestCase(GuildRoleFixture):
    @patch(CLIENT)
    def test_snapshot_marks_roles_the_bot_can_assign(self, client_cls):
        client = client_cls.for_guild.return_value
        client.get_current_user.return_value = {"id": "5"}
        client.get_user.return_value = {
            "roles": ["2"],
            "permissions": str(1 << 28),
        }
        client.get_roles.return_value = [
            {"id": "4242", "name": "@everyone", "position": 0},
            {"id": "2", "name": "Bot", "position": 5, "managed": True},
            {"id": str(ROLE_MEMBER), "name": "Members", "position": 1},
            {"id": str(ROLE_DIRECTOR), "name": "High", "position": 6},
        ]
        self.map("director", ROLE_DIRECTOR)
        self.assertTrue(snapshot_guild_roles(self.guild))
        self.guild.refresh_from_db()
        by_id = {row["id"]: row for row in self.guild.roles}
        self.assertTrue(by_id[str(ROLE_MEMBER)]["assignable"])
        self.assertFalse(by_id[str(ROLE_DIRECTOR)]["assignable"])
        self.assertFalse(by_id["4242"]["assignable"])
        self.assertEqual(
            "above_bot",
            self.guild.role_mappings.get(state="director").problem,
        )

    def test_a_tribe_server_stays_out_of_admin_channel_pickers(self):
        tribe = Tribe.objects.create(
            name="Caps", slug="caps-picker", discord_guild=self.guild
        )
        self.corporation.discord_guild = None
        self.corporation.save()
        self.assertNotIn(self.guild, admin_picker_guilds())
        self.guild.is_primary = True
        self.guild.save()
        self.assertIn(self.guild, admin_picker_guilds())
        tribe.delete()


class RoleEndpointTestCase(GuildRoleFixture):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.guild.roles = [
            {"id": str(ROLE_MEMBER), "name": "Members", "assignable": True},
            {
                "id": str(ROLE_DIRECTOR),
                "name": "Directors",
                "assignable": True,
            },
        ]
        self.guild.roles_checked_at = timezone.now()
        self.guild.save()
        self.auth = {"HTTP_AUTHORIZATION": f"Bearer {make_token(self.user)}"}

    def test_a_director_saves_corporation_roles(self):
        url = (
            "/api/eveonline/corporations/corporations/"
            f"{self.corporation.corporation_id}/discord/roles"
        )
        response = self.client.put(
            url,
            data={
                "mappings": [
                    {"state": "member", "role_id": str(ROLE_MEMBER)},
                    {"state": "director", "role_id": str(ROLE_DIRECTOR)},
                ]
            },
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(200, response.status_code)
        states = {
            row["state"]: row["role_id"]
            for row in response.json()["role_sync"]["mappings"]
        }
        self.assertEqual(str(ROLE_MEMBER), states["member"])
        self.assertEqual(str(ROLE_DIRECTOR), states["director"])

        other = User.objects.create(username="member")
        denied = self.client.put(
            url,
            data={"mappings": []},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {make_token(other)}",
        )
        self.assertEqual(403, denied.status_code)

    def test_a_chief_maps_tribe_roles_and_not_offices(self):
        tribe = Tribe.objects.create(
            name="Caps",
            slug="caps-api",
            chief=self.user,
            discord_guild=self.guild,
        )
        self.corporation.discord_guild = None
        self.corporation.discord_bot_status = ""
        self.corporation.save()
        detail = self.client.get(f"/api/tribes/{tribe.pk}", **self.auth)
        self.assertTrue(detail.json()["can_manage_discord"])
        stranger = User.objects.create(username="pilot")
        hidden = self.client.get(
            f"/api/tribes/{tribe.pk}",
            HTTP_AUTHORIZATION=f"Bearer {make_token(stranger)}",
        )
        self.assertFalse(hidden.json()["can_manage_discord"])

        url = f"/api/tribes/{tribe.pk}/discord"
        denied = self.client.get(
            url, HTTP_AUTHORIZATION=f"Bearer {make_token(stranger)}"
        )
        self.assertEqual(403, denied.status_code)
        office = self.client.put(
            url,
            data={
                "mappings": [
                    {"state": "director", "role_id": str(ROLE_DIRECTOR)}
                ]
            },
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(400, office.status_code)
        self.assertEqual("state_not_allowed", office.json()["detail"])
        saved = self.client.put(
            url,
            data={
                "mappings": [{"state": "member", "role_id": str(ROLE_MEMBER)}]
            },
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(200, saved.status_code)
        self.assertEqual("Members", saved.json()["roles"][0]["name"])
