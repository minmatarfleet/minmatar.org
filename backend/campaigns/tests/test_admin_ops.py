"""Admin operator actions and default-arc helpers for campaigns."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.test import RequestFactory
from django.utils import timezone

from app.test import TestCase
from campaigns.admin import CampaignAdmin
from campaigns.services.refresh import refresh_campaign
from campaigns.helpers import ensure_default_arc
from campaigns.models import (
    Campaign,
    CampaignKind,
    CampaignStructure,
    CampaignSystem,
    CampaignSystemArc,
    CampaignSystemSnapshot,
    CampaignWeekTarget,
    SystemGoal,
)
from campaigns.tests.helpers import KAMELA, make_campaign
from structures.admin import StructureTimerAdmin
from structures.models import EveStructureTimer


class EnsureDefaultArcTestCase(TestCase):
    def test_creates_arc_for_fw_objective_with_goal(self):
        campaign = make_campaign()
        system = campaign.systems.first()
        CampaignSystemArc.objects.filter(campaign_system=system).delete()

        self.assertTrue(ensure_default_arc(system))
        arc = CampaignSystemArc.objects.get(campaign_system=system)
        self.assertEqual(arc.target_state, "flip")
        self.assertEqual(arc.due_at, campaign.end_at)

    def test_hold_goal_gets_hold_arc(self):
        campaign = make_campaign()
        system = campaign.systems.first()
        system.goal = SystemGoal.HOLD
        system.save(update_fields=["goal"])
        CampaignSystemArc.objects.filter(campaign_system=system).delete()

        self.assertTrue(ensure_default_arc(system))
        self.assertEqual(
            CampaignSystemArc.objects.get(campaign_system=system).target_state,
            "hold",
        )

    def test_skips_ops_theaters_and_none_goal(self):
        campaign = make_campaign(kind=CampaignKind.STRATEGIC)
        system = campaign.systems.first()
        system.goal = SystemGoal.NONE
        system.is_fw_objective = False
        system.save(update_fields=["goal", "is_fw_objective"])
        CampaignSystemArc.objects.filter(campaign_system=system).delete()

        self.assertFalse(ensure_default_arc(system))
        self.assertFalse(
            CampaignSystemArc.objects.filter(campaign_system=system).exists()
        )

    def test_skips_scout_goal(self):
        campaign = make_campaign()
        system = campaign.systems.first()
        system.goal = SystemGoal.RECON
        system.save(update_fields=["goal"])
        CampaignSystemArc.objects.filter(campaign_system=system).delete()

        self.assertFalse(ensure_default_arc(system))
        self.assertFalse(
            CampaignSystemArc.objects.filter(campaign_system=system).exists()
        )

    def test_signal_creates_arc_on_system_save(self):
        campaign = make_campaign()
        CampaignSystem.objects.filter(campaign=campaign).delete()
        system = CampaignSystem.objects.create(
            campaign=campaign,
            solar_system_id=KAMELA,
            name="Kamela",
            goal=SystemGoal.TAKE,
            is_fw_objective=True,
        )
        self.assertTrue(
            CampaignSystemArc.objects.filter(campaign_system=system).exists()
        )

    def test_ensure_is_idempotent(self):
        campaign = make_campaign()
        system = campaign.systems.first()
        self.assertFalse(ensure_default_arc(system))
        self.assertEqual(
            1,
            CampaignSystemArc.objects.filter(campaign_system=system).count(),
        )


class CampaignAdminActionsTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_superuser(
            username="campaign-admin",
            email="admin@example.com",
            password="test",
        )
        self.admin = CampaignAdmin(Campaign, AdminSite())
        self.campaign = make_campaign(
            tagline="Take Kamela",
            commander_order_text="",
            commander_order_is_draft=True,
        )

    def test_propose_week_targets_action(self):
        request = self.factory.post("/admin/")
        request.user = self.user
        self.admin.message_user = lambda *args, **kwargs: None
        queryset = Campaign.objects.filter(pk=self.campaign.pk)
        self.admin.propose_week_targets(request, queryset)
        self.assertTrue(
            CampaignWeekTarget.objects.filter(
                campaign_system__campaign=self.campaign
            ).exists()
        )

    def test_draft_and_publish_commander_order_actions(self):
        request = self.factory.post("/admin/")
        request.user = self.user
        self.admin.message_user = lambda *args, **kwargs: None
        queryset = Campaign.objects.filter(pk=self.campaign.pk)

        self.admin.draft_commander_orders(request, queryset)
        self.campaign.refresh_from_db()
        self.assertTrue(self.campaign.commander_order_text)
        self.assertTrue(self.campaign.commander_order_is_draft)

        self.admin.publish_commander_orders(request, queryset)
        self.campaign.refresh_from_db()
        self.assertFalse(self.campaign.commander_order_is_draft)


class CampaignAdminTabsTestCase(TestCase):
    """Campaign change form is split into django-admin-tabs."""

    def setUp(self):
        self.user = User.objects.create_superuser(
            username="campaign-tabs",
            email="tabs@example.com",
            password="test",
        )
        self.client.force_login(self.user)
        self.campaign = make_campaign(slug="tabbed-ux", short_code="TBX")

    def test_change_redirects_to_overview_tab(self):
        response = self.client.get(
            f"/admin/campaigns/campaign/{self.campaign.pk}/change/"
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(
            f"/admin/campaigns/campaign/{self.campaign.pk}/tabs/overview/",
            response["Location"],
        )

    def test_overview_and_story_tabs_render(self):
        for slug in ("overview", "story", "settings"):
            with self.subTest(tab=slug):
                response = self.client.get(
                    f"/admin/campaigns/campaign/{self.campaign.pk}/"
                    f"tabs/{slug}/"
                )
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "django-admin-tabs-nav")
                self.assertContains(response, "Overview")
                self.assertContains(response, "Story")
                self.assertContains(response, "Theater")
                self.assertNotContains(response, ">Doctrine<")

    def test_story_tab_has_title_and_cover(self):
        response = self.client.get(
            f"/admin/campaigns/campaign/{self.campaign.pk}/tabs/story/"
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="name"')
        self.assertContains(response, "Title")
        self.assertContains(response, 'name="tagline"')
        self.assertContains(response, 'name="cover_image_url"')
        self.assertContains(response, "campaign-cover-picker")
        self.assertContains(response, "/images/home-auga-cover.jpg")
        self.assertContains(response, "Auga")
        self.assertContains(response, 'name="commander_order_text"')

    def test_story_tab_can_save_gallery_cover(self):
        response = self.client.post(
            f"/admin/campaigns/campaign/{self.campaign.pk}/tabs/story/",
            {
                "name": self.campaign.name,
                "tagline": "Focus",
                "description_md": "",
                "cover_image_url": "/images/home-auga-cover.jpg",
                "commander_order_text": "",
                "commander_order_is_draft": "on",
                "commander_order_set_at": "",
                "_continue": "Save",
            },
        )
        self.assertIn(response.status_code, (200, 302))
        self.campaign.refresh_from_db()
        self.assertEqual(
            self.campaign.cover_image_url, "/images/home-auga-cover.jpg"
        )

    def test_overview_tab_is_read_only_summary(self):
        response = self.client.get(
            f"/admin/campaigns/campaign/{self.campaign.pk}/tabs/overview/"
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "At a glance")
        self.assertContains(response, "Pulse")
        self.assertNotContains(response, 'name="name"')
        self.assertNotContains(response, 'name="slug"')
        self.assertNotContains(response, 'name="status"')
        self.assertNotContains(response, 'name="cover_image_url"')
        self.assertNotContains(response, 'name="_save"')

    def test_settings_tab_has_lifecycle_fields(self):
        response = self.client.get(
            f"/admin/campaigns/campaign/{self.campaign.pk}/tabs/settings/"
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="slug"')
        self.assertContains(response, 'name="status"')
        self.assertContains(response, 'name="discord_channel_id"')
        self.assertContains(response, "Refresh live data")
        self.assertNotContains(response, 'name="name"')
        self.assertNotContains(response, 'name="tagline"')

    def test_settings_refresh_posts_and_returns(self):
        with patch(
            "campaigns.admin.refresh_service.refresh_campaign",
            return_value={
                "killmails_attributed": 2,
                "snapshots": 1,
                "advantage": 1,
                "stats": 3,
            },
        ) as refresh:
            response = self.client.post(
                f"/admin/campaigns/campaign/{self.campaign.pk}/refresh/"
            )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/tabs/settings/", response["Location"])
        refresh.assert_called_once()

    @patch("campaigns.services.snapshots.fetch_fw_systems", return_value=[])
    @patch(
        "campaigns.services.frontlines.fetch_warzone_status", return_value=[]
    )
    def test_refresh_campaign_summarizes_without_esi(self, status, systems):
        result = refresh_campaign(self.campaign)
        self.assertEqual(result["snapshots"], 0)
        self.assertEqual(result["advantage"], 0)
        self.assertEqual(result["snapshots_missing"], [])
        self.assertIn("killmails_scanned", result)

    @patch("campaigns.services.frontlines.fetch_warzone_status")
    @patch("campaigns.services.snapshots.fetch_fw_systems")
    def test_refresh_writes_every_theater_system(self, fetch_fw, fetch_status):
        aug = CampaignSystem.objects.create(
            campaign=self.campaign,
            solar_system_id=30002542,
            name="Auga",
            goal=SystemGoal.HOLD,
            is_fw_objective=True,
        )
        huola = CampaignSystem.objects.create(
            campaign=self.campaign,
            solar_system_id=30003070,
            name="Huola",
            goal=SystemGoal.RECON,
            is_fw_objective=False,
        )

        def fw_row(system_id, points):
            return {
                "solar_system_id": system_id,
                "victory_points": points,
                "victory_points_threshold": 100,
                "owner_faction_id": 500003,
                "occupier_faction_id": 500003,
                "contested": "contested",
            }

        # ESI sometimes returns the id as a string. Both theater systems
        # that appear in the feed must still be written.
        fetch_fw.return_value = [
            fw_row(KAMELA, 10),
            fw_row("30002542", 40),
        ]
        fetch_status.return_value = [
            {
                "solarsystemID": KAMELA,
                "advantage": [
                    {"factionID": 500002, "totalAmount": 12},
                    {"factionID": 500003, "totalAmount": 4},
                ],
            },
            {
                "solarsystemID": "30002542",
                "advantage": [
                    {"factionID": 500002, "totalAmount": 8},
                    {"factionID": 500003, "totalAmount": 20},
                ],
            },
        ]

        result = refresh_campaign(self.campaign)

        self.assertEqual(result["theater_systems"], 3)
        self.assertEqual(result["snapshots"], 2)
        self.assertEqual(result["snapshots_missing"], ["Huola"])
        self.assertEqual(result["advantage"], 2)
        self.assertEqual(
            CampaignSystemSnapshot.objects.filter(
                campaign_system__campaign=self.campaign
            ).count(),
            2,
        )
        aug_snapshot = CampaignSystemSnapshot.objects.get(campaign_system=aug)
        self.assertEqual(aug_snapshot.victory_points, 40)
        self.assertFalse(
            CampaignSystemSnapshot.objects.filter(
                campaign_system=huola
            ).exists()
        )

    def test_theaters_tab_lists_campaign_systems(self):
        system = self.campaign.systems.first()
        response = self.client.get(
            f"/admin/campaigns/campaign/{self.campaign.pk}/tabs/theater/"
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, system.name)
        self.assertContains(response, "django-admin-tabs-nav")
        self.assertContains(response, "Systems")
        self.assertContains(response, "Constellations")
        self.assertContains(response, "Regions")

    def test_admin_tabs_registered(self):
        self.assertEqual(len(CampaignAdmin.admin_tabs), 6)
        self.assertNotIn(
            "Doctrine",
            [tab.admin_tab_name for tab in CampaignAdmin.admin_tabs],
        )
        self.assertNotIn(
            "Areas",
            [tab.admin_tab_name for tab in CampaignAdmin.admin_tabs],
        )


class StructureTimerAdminAttachTestCase(TestCase):
    """Setting campaign on a timer in admin must create CampaignStructure."""

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_superuser(
            username="timer-admin",
            email="timer@example.com",
            password="test",
        )
        self.admin = StructureTimerAdmin(EveStructureTimer, AdminSite())
        self.campaign = make_campaign(
            kind=CampaignKind.STRATEGIC,
            slug="timer-link",
            short_code="TLK",
        )
        self.campaign.systems.all().delete()
        self.timer = EveStructureTimer.objects.create(
            name="WATERMELLON",
            state="armor",
            type="fortizar",
            timer=timezone.now() + timedelta(days=1),
            system_name="Kamela",
            corporation_name="CVA",
            created_by=self.user,
        )

    def test_save_model_with_campaign_attaches_structure(self):
        request = self.factory.post("/admin/")
        request.user = self.user
        self.timer.campaign = self.campaign
        self.admin.save_model(request, self.timer, form=None, change=True)

        self.timer.refresh_from_db()
        self.assertEqual(self.timer.campaign_id, self.campaign.id)
        self.assertTrue(
            CampaignStructure.objects.filter(
                campaign=self.campaign,
                name="WATERMELLON",
                structure_type="fortizar",
            ).exists()
        )
        self.assertTrue(self.campaign.systems.filter(name="Kamela").exists())
