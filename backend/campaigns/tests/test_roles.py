"""Campaign roles: mirrored from the coordination Discord, they open an
undisclosed campaign to their holders and gate what each may change."""

import json
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.utils import timezone

from campaigns.models import (
    CampaignRole,
    CampaignRoleKind,
    CampaignRoleMember,
    CampaignStatus,
)
from campaigns.services import disclosure
from campaigns.services import roles as role_service
from campaigns.tests.helpers import auth_headers, grant, make_campaign
from discord.models import DiscordUser
from eveonline.models import EveCharacter, EvePlayer

BASE = "/api/campaigns"
SERVER = 555
FC_ROLE = 7001
RECON_ROLE = 7002
EVERYONE_FC = 7003


def _member(discord_id, *role_ids, nick=""):
    return {
        "user": {"id": str(discord_id), "username": f"user{discord_id}"},
        "nick": nick,
        "roles": [str(role_id) for role_id in role_ids],
    }


def _fake_client(members, roles=None):
    client = MagicMock()
    client.get_roles.return_value = roles or [
        {"id": str(FC_ROLE), "name": "FC", "position": 3},
        {"id": str(RECON_ROLE), "name": "Recon", "position": 2},
        {"id": "7004", "name": "Coordinator", "position": 5},
        {"id": "7005", "name": "Diplomat", "position": 4},
    ]
    client.get_members.return_value = members
    return client


class RolesTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        now = timezone.now()
        self.campaign = make_campaign(
            slug="operation-anvil",
            short_code="ANV",
            name="Operation Anvil",
            kind="strategic",
            status=CampaignStatus.SCHEDULED,
            start_at=now + timedelta(days=7),
            end_at=now + timedelta(days=60),
            undisclosed=True,
        )
        self.campaign.coordination_guild_id = SERVER
        self.campaign.save(update_fields=["coordination_guild_id"])
        self.manager = User.objects.create(username="director")
        grant(self.manager, "view_campaign", "change_campaign")
        self.member = User.objects.create(username="member")
        grant(self.member, "view_campaign")
        self.pilot = User.objects.create(username="pilot")
        grant(self.pilot, "view_campaign")
        character = EveCharacter.objects.create(
            character_id=4001, character_name="Pilot Main", user=self.pilot
        )
        EvePlayer.objects.create(user=self.pilot, primary_character=character)
        DiscordUser.objects.create(
            id=111, discord_tag="pilot", user=self.pilot
        )

    def _sync(self, members, roles=None):
        client = _fake_client(members, roles)
        with patch.object(role_service, "_client", return_value=client):
            counts = role_service.sync(self.campaign)
        return client, counts

    def test_sync_matches_roles_by_name_and_mirrors_holders(self):
        _, counts = self._sync(
            [_member(111, FC_ROLE), _member(222, RECON_ROLE, nick="Scout")]
        )
        self.assertEqual(counts["fc"], 1)
        self.assertEqual(counts["recon"], 1)
        fc = CampaignRole.objects.get(campaign=self.campaign, kind="fc")
        self.assertEqual(fc.discord_role_id, FC_ROLE)
        [holder] = fc.members.all()
        self.assertEqual(holder.user, self.pilot)
        self.assertEqual(holder.character_name, "Pilot Main")
        [scout] = CampaignRoleMember.objects.filter(role__kind="recon")
        self.assertIsNone(scout.user)
        self.assertEqual(scout.discord_name, "Scout")

    def test_discord_wins_a_holder_who_lost_the_role_is_dropped(self):
        self._sync([_member(111, FC_ROLE)])
        self._sync([_member(111)])
        self.assertFalse(
            CampaignRoleMember.objects.filter(role__kind="fc").exists()
        )

    def test_our_own_server_is_never_matched_by_name(self):
        self.campaign.coordination_guild_id = None
        self.campaign.save(update_fields=["coordination_guild_id"])
        _, counts = self._sync(
            [_member(111, EVERYONE_FC)],
            roles=[{"id": str(EVERYONE_FC), "name": "FC"}],
        )
        self.assertIsNone(counts["fc"])
        self.assertFalse(CampaignRoleMember.objects.exists())

    def test_role_holder_sees_the_undisclosed_campaign(self):
        self.assertFalse(disclosure.sees_details(self.pilot, self.campaign))
        self._sync([_member(111, FC_ROLE)])
        self.assertTrue(disclosure.sees_details(self.pilot, self.campaign))
        body = self.client.get(
            f"{BASE}/{self.campaign.slug}", **auth_headers(self.pilot)
        ).json()
        self.assertEqual(body["viewer_role"], "coordinator")
        self.assertEqual(body["viewer_roles"], ["fc"])
        self.assertEqual(body["can_edit"], ["fleets"])
        self.assertIn("fleets", body["coordinator_scopes"])
        self.assertNotIn("sides", body["coordinator_scopes"])

    def test_scopes_follow_the_role(self):
        self._sync([_member(111, RECON_ROLE)])
        timers = self.client.get(
            f"{BASE}/{self.campaign.slug}/timers", **auth_headers(self.pilot)
        )
        self.assertEqual(timers.status_code, 200)
        fleets = self.client.get(
            f"{BASE}/{self.campaign.slug}/fleets", **auth_headers(self.pilot)
        )
        self.assertEqual(fleets.status_code, 403)

    def test_diplomat_edits_sides_recon_does_not(self):
        payload = {
            "kind": "alliance",
            "side": "enemy",
            "alliance_id": 1988009451,
            "name": "Curatores Veritatis Alliance",
        }
        self._sync([_member(111, RECON_ROLE)])
        refused = self.client.post(
            f"{BASE}/{self.campaign.slug}/parties",
            json.dumps(payload),
            content_type="application/json",
            **auth_headers(self.pilot),
        )
        self.assertEqual(refused.status_code, 403)
        self._sync([_member(111, 7005)])
        allowed = self.client.post(
            f"{BASE}/{self.campaign.slug}/parties",
            json.dumps(payload),
            content_type="application/json",
            **auth_headers(self.pilot),
        )
        self.assertNotEqual(allowed.status_code, 403)

    def test_members_cannot_read_the_rosters(self):
        response = self.client.get(
            f"{BASE}/{self.campaign.slug}/roles", **auth_headers(self.member)
        )
        self.assertEqual(response.status_code, 403)

    def test_manager_reads_rosters_and_can_map(self):
        with patch.object(
            role_service,
            "discord_roles",
            return_value=[{"id": str(FC_ROLE), "name": "FC"}],
        ):
            body = self.client.get(
                f"{BASE}/{self.campaign.slug}/roles",
                **auth_headers(self.manager),
            ).json()
        self.assertEqual(
            [role["kind"] for role in body["roles"]],
            ["coordinator", "fc", "diplomat", "recon"],
        )
        self.assertTrue(body["can_map"])
        self.assertTrue(body["can_change"])

    def test_fc_cannot_change_rosters(self):
        self._sync([_member(111, FC_ROLE)])
        body = self.client.get(
            f"{BASE}/{self.campaign.slug}/roles", **auth_headers(self.pilot)
        ).json()
        self.assertFalse(body["can_change"])
        self.assertFalse(body["can_map"])
        response = self.client.post(
            f"{BASE}/{self.campaign.slug}/roles/sync",
            **auth_headers(self.pilot),
        )
        self.assertEqual(response.status_code, 403)

    def test_site_added_character_gets_the_discord_role_then_follows_it(self):
        CampaignRole.objects.create(
            campaign=self.campaign, kind="fc", discord_role_id=FC_ROLE
        )
        with patch(
            "campaigns.services.coordinators.lookup",
            return_value={
                "character_id": 4001,
                "character_name": "Pilot Main",
                "corporation_name": "",
                "alliance_name": "",
            },
        ):
            role_service.add_character(
                self.campaign, "fc", "Pilot Main", self.manager
            )
        # Pending rows already count on the site.
        self.assertEqual(
            role_service.kinds_for(self.pilot, self.campaign), {"fc"}
        )
        client, _ = self._sync([_member(111)])
        client.add_user_role.assert_called_once_with(111, FC_ROLE)
        [row] = CampaignRoleMember.objects.filter(role__kind="fc")
        self.assertEqual(row.source, "discord")
        self.assertEqual(row.discord_user_id, 111)

    def test_removing_takes_the_discord_role_away(self):
        self._sync([_member(111, FC_ROLE)])
        member = CampaignRoleMember.objects.get(role__kind="fc")
        client = MagicMock()
        with patch.object(role_service, "_client", return_value=client):
            role_service.remove_member(member)
        client.remove_user_role.assert_called_once_with(111, FC_ROLE)
        self.assertFalse(CampaignRoleMember.objects.exists())

    def test_role_kinds_cover_the_four_roles(self):
        self.assertEqual(set(role_service.KINDS), set(CampaignRoleKind.values))
        self.assertEqual(set(role_service.READS), set(CampaignRoleKind.values))
        self.assertEqual(set(role_service.EDITS), set(CampaignRoleKind.values))
