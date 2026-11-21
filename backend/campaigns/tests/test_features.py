"""Feature switches: kind presets, the migration, and the settings patch."""

import importlib
import json

from django.apps import apps
from django.contrib.auth.models import User
from django.test import Client, TestCase

from campaigns.models import Campaign, CampaignKind
from campaigns.tests.helpers import auth_headers, grant, make_campaign

BASE = "/api/campaigns"


class FeaturePresetTestCase(TestCase):
    def test_faction_warfare_preset(self):
        campaign = make_campaign()
        self.assertEqual(
            campaign.features,
            {
                "weekly_progress": True,
                "structures": False,
                "timers": False,
                "theater": True,
                "fleets": True,
                "destruction": False,
                "pilots": True,
                "projects": True,
            },
        )

    def test_strategic_preset(self):
        campaign = make_campaign(kind=CampaignKind.STRATEGIC)
        self.assertEqual(
            campaign.features,
            {
                "weekly_progress": False,
                "structures": True,
                "timers": True,
                "theater": False,
                "fleets": True,
                "destruction": True,
                "pilots": False,
                "projects": False,
            },
        )

    def test_explicit_switch_beats_the_preset(self):
        campaign = make_campaign(
            kind=CampaignKind.STRATEGIC, destruction_enabled=False
        )
        self.assertFalse(campaign.destruction_enabled)
        self.assertTrue(campaign.timers_enabled)

    def test_saving_again_keeps_the_switches(self):
        campaign = make_campaign()
        campaign.timers_enabled = True
        campaign.save()
        campaign = Campaign.objects.get(pk=campaign.pk)
        campaign.save()
        campaign.refresh_from_db()
        self.assertTrue(campaign.timers_enabled)


class FeatureMigrationTestCase(TestCase):
    def test_existing_campaigns_keep_todays_tabs(self):
        fw = make_campaign(slug="old-fw", short_code="OFW")
        strategic = make_campaign(
            slug="old-strat", short_code="OST", kind=CampaignKind.STRATEGIC
        )
        migration = importlib.import_module(
            "campaigns.migrations.0035_campaign_features"
        )
        migration.existing_campaigns_keep_their_tabs(apps, None)
        fw.refresh_from_db()
        strategic.refresh_from_db()
        for campaign in (fw, strategic):
            self.assertTrue(campaign.weekly_progress_enabled)
            self.assertTrue(campaign.theater_enabled)
            self.assertTrue(campaign.fleets_enabled)
            self.assertTrue(campaign.pilots_enabled)
            self.assertTrue(campaign.projects_enabled)
            self.assertFalse(campaign.timers_enabled)
            self.assertFalse(campaign.destruction_enabled)
        self.assertFalse(fw.structures_enabled)
        self.assertTrue(strategic.structures_enabled)


class FeatureSettingsApiTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.campaign = make_campaign()
        self.manager = User.objects.create(username="director")
        grant(self.manager, "change_campaign", "view_campaign")
        self.url = f"{BASE}/{self.campaign.slug}"

    def test_patch_switches_only_named_features(self):
        response = self.client.patch(
            f"{self.url}/settings",
            data=json.dumps({"features": {"timers": True, "pilots": False}}),
            content_type="application/json",
            **auth_headers(self.manager),
        )
        self.assertEqual(response.status_code, 200)
        features = response.json()["features"]
        self.assertTrue(features["timers"])
        self.assertFalse(features["pilots"])
        self.assertTrue(features["theater"])
        self.campaign.refresh_from_db()
        self.assertTrue(self.campaign.timers_enabled)
        self.assertFalse(self.campaign.pilots_enabled)

    def test_detail_carries_features(self):
        response = self.client.get(self.url, **auth_headers(self.manager))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["features"], self.campaign.features)
