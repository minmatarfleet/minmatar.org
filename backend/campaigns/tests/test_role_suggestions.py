"""Inviting from the coordination Discord: every server member with the
character they most likely fly, and a role given in one click."""

import json
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase
from django.utils import timezone

from campaigns.models import CampaignRole, CampaignRoleMember, CampaignStatus
from campaigns.services import disclosure
from campaigns.services import role_suggestions
from campaigns.services import roles as role_service
from campaigns.tests.helpers import auth_headers, grant, make_campaign
from discord.models import DiscordUser
from eveonline.models import EveCharacter, EvePlayer

BASE = "/api/campaigns"
SERVER = 555
FC_ROLE = 7001


def _member(discord_id, *role_ids, nick="", global_name="", bot=False):
    return {
        "user": {
            "id": str(discord_id),
            "username": f"user{discord_id}",
            "global_name": global_name,
            "bot": bot,
        },
        "nick": nick,
        "roles": [str(role_id) for role_id in role_ids],
    }


def _ok(data=None, results=None):
    response = MagicMock()
    response.success.return_value = True
    response.data = data
    response.results.return_value = results or []
    return response


class CandidateNamesTestCase(TestCase):
    def test_tickers_and_decorations_are_dropped(self):
        self.assertEqual(
            role_suggestions.candidate_names(
                {"nick": "[FL33T] Jane Doe | FC", "user": {}}
            ),
            ["Jane Doe"],
        )
        self.assertIn(
            "Jane Doe",
            role_suggestions.candidate_names(
                {"nick": "Jane Doe (alt)", "user": {}}
            ),
        )
        self.assertEqual(
            role_suggestions.candidate_names(
                {"nick": "", "user": {"username": "x"}}
            ),
            [],
        )

    def test_hyphenated_names_stay_whole(self):
        self.assertEqual(
            role_suggestions.candidate_names(
                {"nick": "Jean-Luc Picard", "user": {}}
            )[0],
            "Jean-Luc Picard",
        )


class RoleSuggestionsTestCase(TestCase):
    def setUp(self):
        cache.clear()
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
        # Linked on the site.
        self.pilot = User.objects.create(username="pilot")
        grant(self.pilot, "view_campaign")
        main = EveCharacter.objects.create(
            character_id=4001, character_name="Pilot Main", user=self.pilot
        )
        EvePlayer.objects.create(user=self.pilot, primary_character=main)
        DiscordUser.objects.create(
            id=111, discord_tag="pilot", user=self.pilot
        )
        # On the site, Discord not linked.
        self.friend = User.objects.create(username="friend")
        grant(self.friend, "view_campaign")
        EveCharacter.objects.create(
            character_id=4002,
            character_name="Friendly Fella",
            user=self.friend,
        )
        self.members = [
            _member(111, nick="whatever"),
            _member(222, nick="[ALLY] Friendly Fella"),
            _member(333, global_name="Outside Diplomat | Envoy"),
            _member(444, nick="xX"),
            _member(999, nick="Some Bot", bot=True),
        ]

    def _discord(self):
        client = MagicMock()
        client.get_members.return_value = self.members
        return client

    def _esi(self):
        esi = MagicMock()
        esi.resolve_universe_ids.return_value = _ok(
            {"characters": [{"id": 5003, "name": "Outside Diplomat"}]}
        )
        esi.get_character_affiliations.return_value = _ok(
            results=[
                {
                    "character_id": 5003,
                    "corporation_id": 98000001,
                    "alliance_id": 99000001,
                }
            ]
        )
        esi.resolve_universe_names.return_value = _ok(
            results=[
                {"id": 98000001, "name": "Envoy Corp"},
                {"id": 99000001, "name": "Friendly Alliance"},
            ]
        )
        return esi

    def _get(self, user):
        with patch(
            "discord.client.DiscordClient", return_value=self._discord()
        ), patch("eveonline.client.EsiClient", return_value=self._esi()):
            return self.client.get(
                f"{BASE}/{self.campaign.slug}/roles/suggestions",
                **auth_headers(user),
            )

    def test_every_human_is_matched_to_a_character(self):
        response = self._get(self.manager)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["available"])
        rows = {row["discord_user_id"]: row for row in body["members"]}
        self.assertNotIn("999", rows)
        self.assertEqual(rows["111"]["match"], "linked")
        self.assertEqual(rows["111"]["character_name"], "Pilot Main")
        self.assertEqual(rows["222"]["match"], "site")
        self.assertEqual(rows["222"]["character_id"], 4002)
        self.assertEqual(rows["333"]["match"], "esi")
        self.assertEqual(rows["333"]["character_name"], "Outside Diplomat")
        self.assertEqual(rows["333"]["alliance_name"], "Friendly Alliance")
        self.assertEqual(rows["444"]["match"], "")
        self.assertIsNone(rows["444"]["character_id"])
        # Matched first, then the rest.
        self.assertEqual(body["members"][-1]["discord_user_id"], "444")

    def test_only_people_who_add_role_holders_see_the_list(self):
        self.assertEqual(self._get(self.member).status_code, 403)

    def test_our_alliance_server_is_not_listed(self):
        self.campaign.coordination_guild_id = None
        self.campaign.save(update_fields=["coordination_guild_id"])
        body = self._get(self.manager).json()
        self.assertFalse(body["available"])
        self.assertFalse(body["own_server"])
        self.assertEqual(body["members"], [])

    def _add(self, kind, payload, discord_client=None):
        discord_client = discord_client or self._discord()
        with patch(
            "discord.client.DiscordClient", return_value=discord_client
        ), patch("eveonline.client.EsiClient", return_value=self._esi()):
            return self.client.post(
                f"{BASE}/{self.campaign.slug}/roles/{kind}/members",
                data=json.dumps(payload),
                content_type="application/json",
                **auth_headers(self.manager),
            )

    def test_invite_a_server_member_with_a_mapped_role(self):
        role_service.ensure_roles(self.campaign)
        CampaignRole.objects.filter(campaign=self.campaign, kind="fc").update(
            discord_role_id=FC_ROLE, discord_role_name="FC"
        )
        discord_client = self._discord()
        with patch("campaigns.tasks.sync_campaign_roles.delay"):
            response = self._add(
                "fc", {"discord_user_id": "222"}, discord_client
            )
        self.assertEqual(response.status_code, 200, response.content)
        discord_client.add_user_role.assert_called_once_with(222, FC_ROLE)
        row = CampaignRoleMember.objects.get(role__kind="fc")
        self.assertEqual(row.source, CampaignRoleMember.Source.DISCORD)
        self.assertEqual(row.character_id, 4002)
        self.assertEqual(row.user, self.friend)
        # They see the campaign before it is announced.
        self.assertTrue(disclosure.sees_details(self.friend, self.campaign))

        # A sync keeps the invited character until they link Discord.
        with patch.object(
            role_service, "_client", return_value=discord_client
        ):
            discord_client.get_members.return_value = [
                _member(222, FC_ROLE, nick="[ALLY] Friendly Fella")
            ]
            role_service.sync(self.campaign)
        row = CampaignRoleMember.objects.get(role__kind="fc")
        self.assertEqual(row.character_name, "Friendly Fella")

    def test_invite_without_a_mapped_role_waits_on_discord(self):
        with patch("campaigns.tasks.sync_campaign_roles.delay"):
            response = self._add("diplomat", {"discord_user_id": "333"})
        self.assertEqual(response.status_code, 200, response.content)
        row = CampaignRoleMember.objects.get(role__kind="diplomat")
        self.assertEqual(row.source, CampaignRoleMember.Source.SITE)
        self.assertEqual(row.discord_user_id, 333)
        self.assertEqual(row.character_name, "Outside Diplomat")
        self.assertEqual(row.corporation_name, "Envoy Corp")

    def test_a_member_with_no_guess_needs_a_character(self):
        response = self._add("recon", {"discord_user_id": "444"})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(CampaignRoleMember.objects.exists())

    def test_someone_not_on_the_server_is_refused(self):
        response = self._add("recon", {"discord_user_id": "123456"})
        self.assertEqual(response.status_code, 400)

    def test_held_roles_are_listed(self):
        with patch("campaigns.tasks.sync_campaign_roles.delay"):
            self._add("diplomat", {"discord_user_id": "333"})
        rows = {
            row["discord_user_id"]: row
            for row in self._get(self.manager).json()["members"]
        }
        self.assertEqual(rows["333"]["roles"], ["diplomat"])
        self.assertEqual(rows["222"]["roles"], [])

    def test_invited_owner_is_told_their_role(self):
        with patch("notifications.service.notify_user") as notify, patch(
            "campaigns.tasks.sync_campaign_roles.delay"
        ):
            self._add("fc", {"discord_user_id": "222"})
        notify.assert_called_once()
        self.assertEqual(notify.call_args.args[0], self.friend)
        self.assertEqual(notify.call_args.args[2]["role"], "fc")

    def test_a_saved_invite_is_not_an_error_when_the_queue_is_down(self):
        with patch(
            "campaigns.tasks.sync_campaign_roles.delay",
            side_effect=ConnectionError("broker down"),
        ):
            response = self._add("diplomat", {"discord_user_id": "333"})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(
            CampaignRoleMember.objects.filter(role__kind="diplomat").exists()
        )


class TagCheckTestCase(TestCase):
    """The ticker a member wears on the server checks the name guess."""

    def setUp(self):
        cache.clear()

    def _esi(self, characters, affiliations, tickers):
        esi = MagicMock()
        esi.resolve_universe_ids.return_value = _ok({"characters": characters})
        esi.get_character_affiliations.return_value = _ok(results=affiliations)
        esi.resolve_universe_names.return_value = _ok(results=[])

        def entity(entity_id):
            return _ok({"ticker": tickers.get(entity_id, "")})

        esi.get_alliance.side_effect = entity
        esi.get_corporation.side_effect = entity
        return esi

    def test_tag_confirms_or_flags_a_name_twin(self):
        esi = self._esi(
            [
                {"id": 1, "name": "Aiel Bladesire"},
                {"id": 2, "name": "Crispy"},
            ],
            [
                {"character_id": 1, "corporation_id": 10, "alliance_id": 20},
                {"character_id": 2, "corporation_id": 11},
            ],
            {20: "FRONT", 10: "QC", 11: "PTS"},
        )
        members = [
            _member(1, nick="[FRONT] Aiel Bladesire"),
            _member(2, nick="[FRONT] Crispy"),
        ]
        with patch("eveonline.client.EsiClient", return_value=esi):
            rows = {
                row["discord_user_id"]: row
                for row in role_suggestions.match_members(members)
            }
        self.assertEqual(rows[1]["tag"], "FRONT")
        self.assertEqual(rows[1]["tag_check"], "match")
        self.assertTrue(role_suggestions.trusted(rows[1]))
        self.assertEqual(rows[2]["tag_check"], "mismatch")
        self.assertFalse(role_suggestions.trusted(rows[2]))
        # The alliance ticker settled Aiel; only Crispy's corporation is
        # looked up.
        esi.get_corporation.assert_called_once_with(11)

    def test_username_only_without_a_server_name(self):
        self.assertEqual(
            role_suggestions.candidate_names(
                {"nick": "[FRONT] Ynot E", "user": {"username": "u12"}}
            ),
            ["Ynot E"],
        )
        self.assertEqual(
            role_suggestions.candidate_names(
                {"nick": "", "user": {"username": "bearthatcares"}}
            ),
            ["bearthatcares"],
        )
