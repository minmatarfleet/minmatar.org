"""The Destruction feature: where kills count, and the Destruction tab."""

from unittest import mock

from django.contrib.auth.models import User
from django.test import Client, TestCase

from campaigns.models import (
    AreaScope,
    CampaignArea,
    CampaignKillmail,
    CampaignKind,
    CampaignStructure,
    KillmailOutcome,
    SystemGoal,
)
from campaigns.services.attribution import attribute_feed_killmail
from campaigns.services.kill_scope import monitor_kill_scope
from campaigns.tests.helpers import (
    auth_headers,
    enlist,
    grant,
    make_campaign,
    make_feed_killmail,
)
from feed.models import FeedMonitoredSystem

AREA_SYSTEM = 30000001
OUTSIDE = 30000099
AREA_SYSTEMS = "campaigns.services.kill_scope.systems_in_area"


class KillScopeTestCase(TestCase):
    def setUp(self):
        self.campaign = make_campaign(
            kind=CampaignKind.STRATEGIC, slug="dest", short_code="DST"
        )
        self.assertTrue(self.campaign.destruction_enabled)
        system = self.campaign.systems.first()
        system.is_fw_objective = False
        system.goal = SystemGoal.NONE
        system.save(update_fields=["is_fw_objective", "goal"])
        CampaignArea.objects.create(
            campaign=self.campaign,
            scope=AreaScope.CONSTELLATION,
            constellation_id=20000001,
            name="Example Constellation",
        )
        enlist(self.campaign, "pilot", 3001)

    def _kill(self, killmail_id, solar_system_id):
        return attribute_feed_killmail(
            make_feed_killmail(
                killmail_id,
                solar_system_id=solar_system_id,
                victim_character_id=9999,
                attacker_ids=[3001],
            )
        )

    def test_ops_system_kill_counts_with_destruction(self):
        with mock.patch(AREA_SYSTEMS, return_value=set()):
            self.assertEqual(self._kill(1, self.campaign.system_ids()[0]), 1)

    def test_area_kill_counts_with_destruction(self):
        with mock.patch(AREA_SYSTEMS, return_value={AREA_SYSTEM}):
            self.assertEqual(self._kill(2, AREA_SYSTEM), 1)
            self.assertEqual(self._kill(3, OUTSIDE), 0)
        self.assertEqual(
            list(
                CampaignKillmail.objects.values_list("killmail_id", flat=True)
            ),
            [2],
        )

    def test_destruction_off_keeps_todays_rule(self):
        self.campaign.destruction_enabled = False
        self.campaign.save(update_fields=["destruction_enabled"])
        with mock.patch(AREA_SYSTEMS, return_value={AREA_SYSTEM}):
            self.assertEqual(self._kill(4, AREA_SYSTEM), 0)
            self.assertEqual(self._kill(5, self.campaign.system_ids()[0]), 0)

    def test_area_systems_are_monitored(self):
        with mock.patch(AREA_SYSTEMS, return_value={AREA_SYSTEM}):
            monitor_kill_scope(self.campaign)
        self.assertTrue(
            FeedMonitoredSystem.objects.filter(
                solar_system_id=AREA_SYSTEM,
                source=FeedMonitoredSystem.Source.CAMPAIGN,
            ).exists()
        )


class DestructionApiTestCase(TestCase):
    def setUp(self):
        self.campaign = make_campaign(kind=CampaignKind.STRATEGIC)
        self.viewer = User.objects.create(username="viewer")
        grant(self.viewer, "view_campaign")
        structure = CampaignStructure.objects.create(
            campaign=self.campaign,
            name="Forward Box",
            structure_type="astrahus",
            solar_system_id=self.campaign.system_ids()[0],
            system_name="Kamela",
            status="destroyed",
        )
        for killmail_id, isk, outcome, linked in (
            (1, 9_000_000_000, KillmailOutcome.KILL, structure),
            (2, 400_000_000, KillmailOutcome.KILL, None),
            (3, 70_000_000_000, KillmailOutcome.LOSS, None),
        ):
            CampaignKillmail.objects.create(
                campaign=self.campaign,
                killmail_id=killmail_id,
                killmail_time=self.campaign.start_at,
                solar_system_id=structure.solar_system_id,
                isk_value=isk,
                outcome=outcome,
                structure=linked,
                is_structure=linked is not None,
                victim_ship_type_id=35832,
            )

    def test_tallies_and_rows_are_kills_only(self):
        response = Client().get(
            f"/api/campaigns/{self.campaign.slug}/destruction",
            **auth_headers(self.viewer),
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["structures_destroyed"], 1)
        self.assertEqual(body["biggest_kill_isk"], 9_000_000_000)
        self.assertEqual(
            sorted(row["killmail_id"] for row in body["rows"]), [1, 2]
        )
        names = {row["killmail_id"]: row["name"] for row in body["rows"]}
        self.assertEqual(names[1], "Forward Box")
