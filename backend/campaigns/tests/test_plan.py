"""The weekly plan and the orders derived from it."""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from campaigns.models import (
    CampaignDailyOrder,
    CampaignSystemArc,
    CampaignSystemSnapshot,
    CampaignWeekTarget,
    OperationalState,
    SystemGoal,
)
from campaigns.services import plan
from campaigns.tests.helpers import enlist, make_campaign


class WeeklyPlanTests(TestCase):
    def setUp(self):
        self.campaign = make_campaign()
        self.system = self.campaign.systems.first()
        CampaignSystemArc.objects.create(
            campaign_system=self.system,
            target_state="flip",
            due_at=self.campaign.end_at,
        )

    def _snapshot(self, hours_ago, victory_points, contested):
        return CampaignSystemSnapshot.objects.create(
            campaign_system=self.system,
            captured_at=timezone.now() - timedelta(hours=hours_ago),
            victory_points=victory_points,
            victory_points_threshold=3000,
            contested_percent=contested,
            operational_state=OperationalState.FRONTLINE,
        )

    def test_a_capture_system_gets_a_victory_point_target(self):
        self._snapshot(1, 900, 30.0)
        plan.propose_week(self.campaign)

        row = CampaignWeekTarget.objects.get(campaign_system=self.system)
        self.assertEqual(row.metric, CampaignWeekTarget.Metric.VICTORY_POINTS)
        self.assertGreater(row.target, 0)
        self.assertTrue(row.proposed)

    def test_the_target_is_never_below_a_reachable_floor(self):
        self._snapshot(1, 0, 0.0)
        plan.propose_week(self.campaign)
        row = CampaignWeekTarget.objects.get(campaign_system=self.system)
        self.assertGreaterEqual(row.target, 3000)

    def test_a_defend_system_is_measured_in_days_under_the_line(self):
        self.system.goal = SystemGoal.DEFEND
        self.system.save()
        plan.propose_week(self.campaign)

        row = CampaignWeekTarget.objects.get(campaign_system=self.system)
        self.assertEqual(row.metric, CampaignWeekTarget.Metric.DAYS_UNDER_LINE)
        self.assertEqual(row.target, 7.0)

    def test_progress_and_pace_are_computed_from_snapshots(self):
        # A baseline from before the week opened, then this week's reading.
        self._snapshot(24 * 9, 500, 16.0)
        self._snapshot(1, 1_100, 36.0)
        plan.propose_week(self.campaign)
        plan.update_week_progress(self.campaign)

        row = CampaignWeekTarget.objects.get(campaign_system=self.system)
        self.assertGreater(row.progress, 0)
        self.assertIn(row.pace, ("behind", "on_pace", "ahead"))

    def test_accepting_a_target_clears_the_proposed_flag(self):
        self._snapshot(1, 900, 30.0)
        plan.propose_week(self.campaign)
        row = CampaignWeekTarget.objects.get(campaign_system=self.system)
        row.proposed = False
        row.target = 5000
        row.save()

        plan.propose_week(self.campaign)
        row.refresh_from_db()
        # An accepted target is never quietly rewritten by the next proposal.
        self.assertEqual(row.target, 5000)


class OrderTests(TestCase):
    def setUp(self):
        self.campaign = make_campaign()
        self.system = self.campaign.systems.first()
        self.user, _ = enlist(self.campaign, "pilot", 4001)
        CampaignSystemSnapshot.objects.create(
            campaign_system=self.system,
            captured_at=timezone.now(),
            victory_points=900,
            victory_points_threshold=3000,
            contested_percent=30.0,
            operational_state=OperationalState.FRONTLINE,
        )
        plan.propose_week(self.campaign)
        plan.update_week_progress(self.campaign)

    def test_orders_are_generated_for_the_day(self):
        created = plan.generate_orders(self.campaign)
        self.assertGreater(created, 0)
        kinds = set(
            CampaignDailyOrder.objects.filter(
                campaign=self.campaign
            ).values_list("kind", flat=True)
        )
        self.assertIn(CampaignDailyOrder.Kind.PLEX, kinds)
        self.assertIn(CampaignDailyOrder.Kind.STANDING_FLEET, kinds)

    def test_orders_are_only_generated_once_a_day(self):
        plan.generate_orders(self.campaign)
        self.assertEqual(plan.generate_orders(self.campaign), 0)

    def test_orders_carry_the_share_of_the_week_they_close(self):
        plan.generate_orders(self.campaign)
        plex = CampaignDailyOrder.objects.filter(
            campaign=self.campaign, kind=CampaignDailyOrder.Kind.PLEX
        ).first()
        self.assertGreaterEqual(plex.gap_share_pct, 0)

    def test_a_pilot_sees_their_own_progress(self):
        plan.generate_orders(self.campaign)
        rows = plan.orders_for(self.campaign, self.user)
        self.assertTrue(rows)
        self.assertFalse(rows[0]["completed"])

    def test_the_commander_order_is_drafted_from_the_plan(self):
        text = plan.draft_commander_order(self.campaign)
        self.assertTrue(text)
        self.assertLessEqual(len(text), 280)
