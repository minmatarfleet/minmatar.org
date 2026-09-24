"""FW objective flag and ops areas on the wire."""

from django.test import TestCase

from campaigns.endpoints import serializers
from campaigns.models import AreaScope, CampaignArea, CampaignKind, SystemGoal
from campaigns.tests.helpers import make_campaign


class TheaterSerializationTests(TestCase):
    def test_system_summary_includes_is_fw_objective(self):
        campaign = make_campaign()
        system = campaign.systems.first()
        summary = serializers.system_summary(system, with_trend=False)
        self.assertTrue(summary["is_fw_objective"])

        system.is_fw_objective = False
        system.goal = SystemGoal.NONE
        system.save(update_fields=["is_fw_objective", "goal"])
        summary = serializers.system_summary(system, with_trend=False)
        self.assertFalse(summary["is_fw_objective"])

    def test_campaign_list_includes_areas(self):
        campaign = make_campaign(
            kind=CampaignKind.STRATEGIC, slug="area-list", short_code="ARL"
        )
        CampaignArea.objects.create(
            campaign=campaign,
            scope=AreaScope.REGION,
            region_id=10000036,
            name="Devoid",
        )
        item = serializers.list_item(campaign, user=None)
        self.assertEqual(len(item["areas"]), 1)
        self.assertEqual(item["areas"][0]["name"], "Devoid")
        self.assertEqual(item["areas"][0]["scope"], "region")
        self.assertEqual(item["areas"][0]["region_id"], 10000036)
