"""Structures and timers reported from a campaign's Discord server."""

import json
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import Permission, User
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from campaigns.models import (
    CampaignDiscordLink,
    CampaignRole,
    CampaignRoleKind,
    CampaignRoleMember,
    CampaignStatus,
    CampaignStructure,
)
from campaigns.services import discord_reports
from campaigns.tests.helpers import KAMELA, auth_headers, make_campaign
from discord.models import DiscordUser
from feed.models import FeedMonitoredSystem
from structures.models import EveStructureTimer

URL = "/api/campaigns/discord/report"
SERVER = 555
ALLY_SERVER = 556
SCOUT = 9001
STRANGER = 9002


def _window(at):
    return (
        "Kamela - Hostile Fort\n0 m\n"
        f"Reinforced until {at.strftime('%Y.%m.%d %H:%M:%S')}"
    )


@override_settings(DISCORD_GUILD_ID="1")
@patch("campaigns.services.discord_posts._queue")
class DiscordReportTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.bot = User.objects.create(username="minmatar-bot")
        self.bot.user_permissions.add(
            Permission.objects.get(codename="service_account")
        )
        self.campaign = make_campaign(coordination_guild_id=SERVER)
        CampaignDiscordLink.objects.create(
            campaign=self.campaign, guild_id=ALLY_SERVER
        )
        FeedMonitoredSystem.objects.update_or_create(
            solar_system_id=KAMELA,
            defaults={"name": "Kamela", "is_active": True},
        )
        recon = CampaignRole.objects.create(
            campaign=self.campaign, kind=CampaignRoleKind.RECON
        )
        # An ally with the Recon role on the server and no site account.
        CampaignRoleMember.objects.create(
            role=recon, discord_user_id=SCOUT, discord_name="Ally Scout"
        )
        self.when = (timezone.now() + timedelta(hours=20)).replace(
            microsecond=0
        )

    def _post(self, user=None, **body):
        payload = {
            "guild_id": SERVER,
            "discord_user_id": SCOUT,
            "kind": "timer",
            "structure_type": "fortizar",
            "timer_state": "armor",
            "selected_item_window": _window(self.when),
            "corporation_name": "Bad Guys Inc",
        }
        payload.update(body)
        return self.client.post(
            URL,
            data=json.dumps(payload),
            content_type="application/json",
            **auth_headers(user or self.bot),
        )

    def test_recon_role_holder_reports_a_timer(self, queue):
        response = self._post()
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIn("Test Push", response.json()["message"])
        timer = EveStructureTimer.objects.get()
        self.assertEqual(timer.campaign, self.campaign)
        self.assertEqual(timer.system_name, "Kamela")
        self.assertEqual(timer.name, "Hostile Fort")
        self.assertEqual(timer.timer, self.when)
        self.assertIsNone(timer.created_by)
        structure = CampaignStructure.objects.get()
        self.assertEqual(structure.timer, timer)
        self.assertEqual(structure.corporation_name, "Bad Guys Inc")

    def test_reports_a_structure_from_a_linked_server(self, queue):
        response = self._post(
            guild_id=ALLY_SERVER,
            kind="structure",
            structure_type="astrahus",
            selected_item_window="Kamela - Staging Astra\n12 km",
            reinforce_hour=19,
        )
        self.assertEqual(response.status_code, 200, response.content)
        structure = CampaignStructure.objects.get()
        self.assertEqual(structure.name, "Staging Astra")
        self.assertEqual(structure.reinforce_hour, 19)
        self.assertFalse(EveStructureTimer.objects.exists())

    def test_stranger_without_role_or_account_is_refused(self, queue):
        response = self._post(discord_user_id=STRANGER)
        self.assertEqual(response.status_code, 403)
        self.assertIn("Recon", response.json()["detail"])
        self.assertFalse(EveStructureTimer.objects.exists())

    def test_linked_site_scout_may_report(self, queue):
        scout = User.objects.create(username="scout")
        scout.user_permissions.add(
            Permission.objects.get(codename="add_evestructuretimer")
        )
        DiscordUser.objects.create(id=STRANGER, discord_tag="s", user=scout)
        response = self._post(discord_user_id=STRANGER)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(EveStructureTimer.objects.get().created_by, scout)

    def test_a_server_without_a_campaign_is_refused(self, queue):
        response = self._post(guild_id=777)
        self.assertEqual(response.status_code, 403)
        self.assertIn("isn't running a campaign", response.json()["detail"])

    def test_finished_campaigns_take_no_reports(self, queue):
        self.campaign.status = CampaignStatus.COMPLETED
        self.campaign.save(update_fields=["status"])
        self.assertEqual(self._post().status_code, 403)

    def test_bad_paste_and_past_timer_are_explained(self, queue):
        response = self._post(selected_item_window="nonsense")
        self.assertEqual(response.status_code, 400)
        self.assertIn("System - Structure name", response.json()["detail"])
        past = timezone.now() - timedelta(days=1)
        response = self._post(selected_item_window=_window(past))
        self.assertEqual(response.status_code, 400)
        self.assertIn("already passed", response.json()["detail"])
        self.assertFalse(EveStructureTimer.objects.exists())

    def test_unknown_system_leaves_no_timer(self, queue):
        window = _window(self.when).replace("Kamela", "Nowhere")
        response = self._post(selected_item_window=window)
        self.assertEqual(response.status_code, 400)
        self.assertIn("Nowhere", response.json()["detail"])
        self.assertFalse(EveStructureTimer.objects.exists())

    def test_two_campaigns_need_a_pick(self, queue):
        other = make_campaign(
            slug="second", short_code="SEC", name="Second Front"
        )
        other.coordination_guild_id = SERVER
        other.save(update_fields=["coordination_guild_id"])
        CampaignRoleMember.objects.create(
            role=CampaignRole.objects.create(
                campaign=other, kind=CampaignRoleKind.COORDINATOR
            ),
            discord_user_id=SCOUT,
        )
        response = self._post()
        self.assertEqual(response.status_code, 403)
        self.assertIn("more than one campaign", response.json()["detail"])
        response = self._post(campaign="SEC")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(EveStructureTimer.objects.get().campaign, other)

    def test_member_tokens_cannot_call_it(self, queue):
        member = User.objects.create(username="member")
        self.assertEqual(self._post(user=member).status_code, 403)

    def test_autocomplete_lists_reportable_campaigns(self, queue):
        response = self.client.get(
            "/api/campaigns/discord/report-campaigns",
            {"guild_id": SERVER, "discord_user_id": SCOUT},
            **auth_headers(self.bot),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(), [{"slug": "test-push", "name": "Test Push"}]
        )
        response = self.client.get(
            "/api/campaigns/discord/report-campaigns",
            {"guild_id": SERVER, "discord_user_id": STRANGER},
            **auth_headers(self.bot),
        )
        self.assertEqual(response.json(), [])


class ParsePlacementTests(TestCase):
    def test_skyhook_paste_names_the_system_and_owner(self):
        placement = discord_reports.parse_placement(
            "Orbital Skyhook (KBP7-G III) [Sukanan Inititive]\n0.5 AU",
            "orbital_skyhook",
        )
        self.assertEqual(placement.system_name, "KBP7-G")
        self.assertEqual(placement.name, "Orbital Skyhook")
        self.assertEqual(placement.owner, "Sukanan Inititive")

    def test_name_with_a_dash_keeps_it(self):
        placement = discord_reports.parse_placement(
            "Amamake - Home - Sweet Home", "astrahus"
        )
        self.assertEqual(placement.system_name, "Amamake")
        self.assertEqual(placement.name, "Home - Sweet Home")
