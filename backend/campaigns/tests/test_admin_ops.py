"""Admin operator actions and default-arc helpers for campaigns."""

from __future__ import annotations

from datetime import timedelta

from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.test import RequestFactory
from django.utils import timezone

from app.test import TestCase
from campaigns.admin import CampaignAdmin
from campaigns.helpers import ensure_default_arc
from campaigns.models import (
    Campaign,
    CampaignKind,
    CampaignStructure,
    CampaignSystem,
    CampaignSystemArc,
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

    def test_defend_goal_gets_hold_arc(self):
        campaign = make_campaign()
        system = campaign.systems.first()
        system.goal = SystemGoal.DEFEND
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

    def test_signal_creates_arc_on_system_save(self):
        campaign = make_campaign()
        CampaignSystem.objects.filter(campaign=campaign).delete()
        system = CampaignSystem.objects.create(
            campaign=campaign,
            solar_system_id=KAMELA,
            name="Kamela",
            goal=SystemGoal.CAPTURE,
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
