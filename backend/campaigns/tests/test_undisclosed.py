"""Undisclosed campaigns: managers and coordinators see them, nobody else.

Everyone else gets an Upcoming Campaign with a start time, by public key,
and nothing in the JSON gives the campaign away.
"""

import json
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from campaigns.models import (
    CampaignCoordinator,
    CampaignDiscordLink,
    CampaignParty,
    CampaignStatus,
    PartySide,
)
from campaigns.services import coordinators as coordinator_service
from campaigns.services import disclosure
from campaigns.tests.helpers import auth_headers, grant, make_campaign
from eveonline.models import EveCharacter
from fittings.models import EveDoctrine, EveDoctrineFitting, EveFitting

BASE = "/api/campaigns"
SECRET = "Operation Sledgehammer"


class UndisclosedTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        now = timezone.now()
        self.campaign = make_campaign(
            slug="operation-sledgehammer",
            short_code="OPS",
            name=SECRET,
            tagline="Burn their keepstars",
            kind="strategic",
            status=CampaignStatus.SCHEDULED,
            start_at=now + timedelta(days=7),
            end_at=now + timedelta(days=90),
            undisclosed=True,
        )
        CampaignParty.objects.create(
            campaign=self.campaign,
            side=PartySide.ENEMY,
            alliance_id=1988009451,
            name="Curatores Veritatis Alliance",
        )
        self.member = User.objects.create(username="member")
        grant(self.member, "view_campaign")
        self.manager = User.objects.create(username="director")
        grant(self.manager, "view_campaign", "change_campaign")
        self.outsider = User.objects.create(username="outsider")
        EveCharacter.objects.create(
            character_id=9001, character_name="Outsider", user=self.outsider
        )

    def _get(self, path, user):
        return self.client.get(f"{BASE}{path}", **auth_headers(user))

    def _coordinate(self, scopes=None):
        CampaignCoordinator.objects.create(
            campaign=self.campaign,
            character_id=9001,
            character_name="Outsider",
        )
        if scopes is not None:
            self.campaign.coordinator_scopes = scopes
            self.campaign.save(update_fields=["coordinator_scopes"])

    def test_list_gives_members_only_an_upcoming_campaign(self):
        response = self._get("", self.member)
        self.assertEqual(response.status_code, 200)
        [row] = response.json()
        self.assertEqual(row["name"], disclosure.GENERIC_NAME)
        self.assertEqual(row["slug"], self.campaign.public_key)
        self.assertTrue(row["undisclosed"])
        self.assertEqual(row["end_at"], row["start_at"])
        self.assertNotIn(SECRET, response.content.decode())
        self.assertNotIn(self.campaign.slug, response.content.decode())
        self.assertNotIn("Curatores", response.content.decode())

    def test_manager_list_shows_the_campaign(self):
        [row] = self._get("", self.manager).json()
        self.assertEqual(row["name"], SECRET)
        self.assertTrue(row["undisclosed"])

    def test_slug_is_a_404_for_members(self):
        response = self._get(f"/{self.campaign.slug}", self.member)
        self.assertEqual(response.status_code, 404)

    def test_public_key_gives_members_the_redacted_detail(self):
        response = self._get(f"/{self.campaign.public_key}", self.member)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["redacted"])
        self.assertEqual(body["name"], disclosure.GENERIC_NAME)
        self.assertEqual(body["parties"], [])
        self.assertEqual(body["kind"], "")
        self.assertNotIn(SECRET, response.content.decode())
        self.assertNotIn("Burn their", response.content.decode())

    def test_sub_resources_are_404_for_members(self):
        for path in ("timers", "fleets", "destruction", "roster"):
            response = self._get(
                f"/{self.campaign.public_key}/{path}", self.member
            )
            self.assertEqual(response.status_code, 404, path)

    def test_members_can_enlist_by_public_key(self):
        EveCharacter.objects.create(
            character_id=42, character_name="Member", user=self.member
        )
        grant(self.member, "add_campaignenlistment")
        response = self.client.post(
            f"{BASE}/{self.campaign.public_key}/enlist",
            data=json.dumps({}),
            content_type="application/json",
            **auth_headers(self.member),
        )
        self.assertNotEqual(response.status_code, 404)

    def test_manager_gets_the_full_detail(self):
        body = self._get(f"/{self.campaign.slug}", self.manager).json()
        self.assertEqual(body["name"], SECRET)
        self.assertFalse(body["redacted"])
        self.assertEqual(body["viewer_role"], "manager")
        self.assertEqual(len(body["parties"]), 1)

    def test_coordinator_sees_only_what_is_shared(self):
        self._coordinate(scopes=["timers"])
        response = self._get(f"/{self.campaign.slug}", self.outsider)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["viewer_role"], "coordinator")
        self.assertEqual(body["name"], SECRET)
        self.assertEqual(body["parties"], [])
        self.assertEqual(
            self._get(
                f"/{self.campaign.slug}/timers", self.outsider
            ).status_code,
            200,
        )
        self.assertEqual(
            self._get(
                f"/{self.campaign.slug}/fleets", self.outsider
            ).status_code,
            403,
        )
        self.assertEqual(
            self._get(
                f"/{self.campaign.slug}/roster", self.outsider
            ).status_code,
            403,
        )

    def test_coordinator_finds_the_campaign_without_the_feature(self):
        self._coordinate()
        [row] = self._get("", self.outsider).json()
        self.assertEqual(row["name"], SECRET)

    def test_overlay_leaves_out_live_undisclosed_campaigns(self):
        self.campaign.status = CampaignStatus.ACTIVE
        self.campaign.start_at = timezone.now() - timedelta(days=1)
        self.campaign.save()
        body = self._get("/overlay", self.member).json()
        self.assertIsNone(body["campaign"])
        self.assertEqual(body["campaigns"], [])
        manager_body = self._get("/overlay", self.manager).json()
        self.assertEqual(len(manager_body["campaigns"]), 1)

    def test_disclosing_shows_everything(self):
        response = self.client.patch(
            f"{BASE}/{self.campaign.slug}/settings",
            data=json.dumps({"undisclosed": False}),
            content_type="application/json",
            **auth_headers(self.manager),
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["undisclosed"])
        body = self._get(f"/{self.campaign.slug}", self.member).json()
        self.assertEqual(body["name"], SECRET)

    def test_unknown_coordinator_scope_is_refused(self):
        response = self.client.patch(
            f"{BASE}/{self.campaign.slug}/settings",
            data=json.dumps({"coordinator_scopes": ["roster"]}),
            content_type="application/json",
            **auth_headers(self.manager),
        )
        self.assertEqual(response.status_code, 400)

    def test_third_party_side(self):
        response = self.client.post(
            f"{BASE}/{self.campaign.slug}/parties",
            data=json.dumps(
                {
                    "name": "Snuffed Out",
                    "kind": "alliance",
                    "side": "third_party",
                    "alliance_id": 99005338,
                }
            ),
            content_type="application/json",
            **auth_headers(self.manager),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["side"], "third_party")


class CoordinatorInviteTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.campaign = make_campaign(undisclosed=True)
        self.manager = User.objects.create(username="director")
        grant(self.manager, "view_campaign", "change_campaign")
        self.member = User.objects.create(username="member")
        grant(self.member, "view_campaign")
        self.url = f"{BASE}/{self.campaign.slug}/coordinators"

    def _invite(self, user, name):
        return self.client.post(
            self.url,
            data=json.dumps({"character_name": name}),
            content_type="application/json",
            **auth_headers(user),
        )

    def test_invites_a_character_from_esi(self):
        with patch.object(
            coordinator_service,
            "lookup",
            return_value={
                "character_id": 777,
                "character_name": "Ally Pilot",
                "corporation_name": "Allied Corp",
                "alliance_name": "C A M E L O T",
            },
        ):
            response = self._invite(self.manager, "ally pilot")
        self.assertEqual(response.status_code, 200)
        [row] = response.json()
        self.assertEqual(row["character_name"], "Ally Pilot")
        self.assertFalse(row["signed_in"])

    def test_unknown_name_is_a_400(self):
        with patch.object(
            coordinator_service,
            "lookup",
            side_effect=coordinator_service.NotFound("x"),
        ):
            response = self._invite(self.manager, "Nobody Here")
        self.assertEqual(response.status_code, 400)

    def test_members_cannot_invite(self):
        response = self._invite(self.member, "Ally Pilot")
        self.assertEqual(response.status_code, 403)

    def test_local_character_resolves_without_esi(self):
        EveCharacter.objects.create(character_id=555, character_name="Known")
        found = coordinator_service.lookup("known")
        self.assertEqual(found["character_id"], 555)

    def test_removing_a_coordinator_drops_their_servers(self):
        user = User.objects.create(username="ally")
        EveCharacter.objects.create(
            character_id=777, character_name="Ally Pilot", user=user
        )
        row = CampaignCoordinator.objects.create(
            campaign=self.campaign, character_id=777, character_name="Ally"
        )
        CampaignDiscordLink.objects.create(
            campaign=self.campaign, guild_id=5, linked_by=user
        )
        response = self.client.delete(
            f"{self.url}/{row.id}", **auth_headers(self.manager)
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.campaign.discord_links.exists())


class DoctrineTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.campaign = make_campaign()
        self.manager = User.objects.create(username="director")
        grant(self.manager, "view_campaign", "change_campaign")
        self.doctrine = EveDoctrine.objects.create(
            name="PHOONS", type="strategic", description=""
        )
        for name, role in (("Typhoon", "primary"), ("Guardian", "support")):
            fitting = EveFitting.objects.create(
                name=name, ship_id=644, description="", eft_format=""
            )
            EveDoctrineFitting.objects.create(
                doctrine=self.doctrine, fitting=fitting, role=role
            )

    def _attach(self):
        return self.client.post(
            f"{BASE}/{self.campaign.slug}/doctrines",
            data=json.dumps({"doctrine_id": self.doctrine.id}),
            content_type="application/json",
            **auth_headers(self.manager),
        )

    def test_attach_brings_in_its_fittings_switched_on(self):
        response = self._attach()
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual([d["name"] for d in body["doctrines"]], ["PHOONS"])
        self.assertEqual(len(body["fittings"]), 2)
        self.assertTrue(all(row["enabled"] for row in body["fittings"]))
        self.assertEqual(
            {row["role_label"] for row in body["fittings"]},
            {"Primary", "Support"},
        )

    def test_switched_off_fittings_leave_the_campaign_page(self):
        row = self._attach().json()["fittings"][0]
        response = self.client.patch(
            f"{BASE}/{self.campaign.slug}/fittings/{row['id']}",
            data=json.dumps({"enabled": False}),
            content_type="application/json",
            **auth_headers(self.manager),
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["enabled"])
        detail = self.client.get(
            f"{BASE}/{self.campaign.slug}", **auth_headers(self.manager)
        ).json()
        self.assertEqual(len(detail["fittings"]), 1)

    def test_detach_removes_its_fittings(self):
        attached = self._attach().json()["doctrines"][0]
        response = self.client.delete(
            f"{BASE}/{self.campaign.slug}/doctrines/{attached['id']}",
            **auth_headers(self.manager),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["fittings"], [])


@override_settings(DISCORD_GUILD_ID=1, DISCORD_CLIENT_ID="bot-client")
class DiscordConnectTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.campaign = make_campaign(undisclosed=True)
        self.manager = User.objects.create(username="director")
        grant(self.manager, "view_campaign", "change_campaign")
        self.coordinator = User.objects.create(username="ally")
        EveCharacter.objects.create(
            character_id=777, character_name="Ally", user=self.coordinator
        )
        CampaignCoordinator.objects.create(
            campaign=self.campaign, character_id=777, character_name="Ally"
        )

    def _connect(self, user, purpose):
        token = auth_headers(user)["HTTP_AUTHORIZATION"].split()[-1]
        return self.client.get(
            f"{BASE}/{self.campaign.slug}/discord/bot/connect",
            {"purpose": purpose, "token": token},
        )

    def test_connect_asks_discord_for_a_code(self):
        response = self._connect(self.coordinator, "link")
        self.assertEqual(response.status_code, 302)
        location = response["Location"]
        self.assertIn("response_type=code", location)
        self.assertIn("permissions=8", location)
        self.assertIn("redirect_uri=", location)

    def test_coordinators_cannot_move_our_server(self):
        self.assertEqual(
            self._connect(self.coordinator, "ours").status_code, 403
        )

    def test_callback_links_the_coordinators_server(self):
        self._connect(self.coordinator, "link")
        state = self.client.session["campaign_discord_bot"]["state"]
        with patch(
            "campaigns.endpoints.get_discord_bot_callback.DiscordClient"
        ) as client:
            client.return_value.exchange_bot_code.return_value = {
                "id": "4242",
                "name": "Allied Ops",
            }
            response = self.client.get(
                f"{BASE}/discord/bot/callback",
                {"code": "abc", "state": state},
            )
        self.assertEqual(response.status_code, 302)
        self.assertIn("discord_bot=connected", response["Location"])
        link = CampaignDiscordLink.objects.get(campaign=self.campaign)
        self.assertEqual(link.guild_id, 4242)
        self.assertEqual(link.linked_by, self.coordinator)

    def test_callback_refuses_a_stale_state(self):
        self._connect(self.coordinator, "link")
        response = self.client.get(
            f"{BASE}/discord/bot/callback", {"code": "abc", "state": "nope"}
        )
        self.assertIn(
            "discord_bot_error=session_expired", response["Location"]
        )
        self.assertFalse(CampaignDiscordLink.objects.exists())

    def test_coordinator_sees_only_their_own_links(self):
        CampaignDiscordLink.objects.create(
            campaign=self.campaign, guild_id=1, linked_by=self.manager
        )
        CampaignDiscordLink.objects.create(
            campaign=self.campaign, guild_id=2, linked_by=self.coordinator
        )
        with patch("campaigns.services.coordination.DiscordClient"):
            response = self.client.get(
                f"{BASE}/{self.campaign.slug}/discord-links",
                **auth_headers(self.coordinator),
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row["guild_id"] for row in response.json()], ["2"])
