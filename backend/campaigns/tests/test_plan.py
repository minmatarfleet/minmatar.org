"""The weekly plan and the orders derived from it."""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from campaigns.constants import DEFAULT_STRUCTURES_REPORTED_TARGET
from campaigns.models import (
    CampaignAdvantageState,
    CampaignDailyOrder,
    CampaignKind,
    CampaignStructure,
    CampaignSystemArc,
    CampaignSystemSnapshot,
    CampaignWeekTarget,
    OperationalState,
    StructureSource,
    StructureStatus,
    SystemGoal,
)
from campaigns.services import plan
from campaigns.tests.helpers import enlist, make_campaign


class WeeklyPlanTests(TestCase):
    def setUp(self):
        self.campaign = make_campaign()
        self.system = self.campaign.systems.first()
        CampaignSystemArc.objects.update_or_create(
            campaign_system=self.system,
            defaults={
                "target_state": "flip",
                "due_at": self.campaign.end_at,
            },
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
        self.system.goal = SystemGoal.HOLD
        self.system.save()
        plan.propose_week(self.campaign)

        row = CampaignWeekTarget.objects.get(campaign_system=self.system)
        self.assertEqual(row.metric, CampaignWeekTarget.Metric.DAYS_UNDER_LINE)
        self.assertEqual(row.target, 7.0)

    def _advantage(self, ours, theirs):
        CampaignAdvantageState.objects.update_or_create(
            campaign_system=self.system,
            defaults={
                "our_pct": ours,
                "enemy_pct": theirs,
                "basis": "reading",
                "reading_age_minutes": 5,
            },
        )
        self.system.refresh_from_db()

    def _task(self, task, target=None):
        self.system.arc.advantage_task = task
        self.system.arc.advantage_target = target
        self.system.arc.save()

    def test_an_arc_without_an_advantage_task_proposes_no_advantage_row(
        self,
    ):
        self._snapshot(1, 900, 30.0)
        plan.propose_week(self.campaign)
        metrics = set(
            CampaignWeekTarget.objects.filter(
                campaign_system=self.system
            ).values_list("metric", flat=True)
        )
        self.assertEqual(metrics, {CampaignWeekTarget.Metric.VICTORY_POINTS})

    def test_gain_advantage_builds_ours_up_to_a_level(self):
        self._task("gain")
        self._advantage(10.0, 40.0)
        self._snapshot(1, 900, 30.0)
        plan.propose_week(self.campaign)

        row = CampaignWeekTarget.objects.get(
            campaign_system=self.system,
            metric=CampaignWeekTarget.Metric.ADVANTAGE_GAIN,
        )
        self.assertEqual(row.target, 75.0)  # the default level
        self.assertEqual(row.baseline, 10.0)
        plan.update_week_progress(self.campaign)
        row.refresh_from_db()
        self.assertEqual(row.progress, 10.0)
        self.assertGreaterEqual(row.pace_expected, 10.0)

    def test_destroy_advantage_knocks_theirs_down_and_lower_is_better(self):
        self._task("destroy", 50.0)
        self._advantage(30.0, 75.0)
        plan.propose_week(self.campaign)
        row = CampaignWeekTarget.objects.get(
            campaign_system=self.system,
            metric=CampaignWeekTarget.Metric.ADVANTAGE_DESTROY,
        )
        self.assertEqual(row.baseline, 75.0)

        # Their level has not moved: behind once the ramp expects movement.
        row.progress = 75.0
        row.pace_expected = 65.0
        self.assertEqual(row.pace, "behind")
        # Already at the target: ahead of any ramp.
        row.progress = 50.0
        self.assertEqual(row.pace, "ahead")

    def test_maintain_advantage_expects_the_level_from_day_one(self):
        self._task("maintain", 90.0)
        self._advantage(81.0, 10.0)
        plan.propose_week(self.campaign)
        plan.update_week_progress(self.campaign)
        row = CampaignWeekTarget.objects.get(
            campaign_system=self.system,
            metric=CampaignWeekTarget.Metric.ADVANTAGE_MAINTAIN,
        )
        self.assertEqual(row.pace_expected, 90.0)
        self.assertEqual(row.progress, 81.0)
        self.assertEqual(row.pace, "on_pace")

    def test_week_position_counts_campaign_weeks(self):
        position = plan.week_position(self.campaign)
        self.assertGreaterEqual(position["week_index"], 1)
        self.assertLessEqual(position["week_index"], position["week_count"])
        self.assertEqual(
            position["week_end"], position["week_start"] + timedelta(days=6)
        )
        self.assertTrue(1 <= position["day_index"] <= 7)

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


class StrategicStructuresReportedTests(TestCase):
    """Structure campaigns get a weekly find-and-report objective."""

    def setUp(self):
        self.campaign = make_campaign(
            kind=CampaignKind.STRATEGIC,
            slug="cva-pressure-test",
            short_code="CVT",
        )
        self.system = self.campaign.systems.first()
        self.system.goal = SystemGoal.NONE
        self.system.is_fw_objective = False
        self.system.save(update_fields=["goal", "is_fw_objective"])

    def test_strategic_ops_systems_get_a_structures_reported_target(self):
        plan.propose_week(self.campaign)
        row = CampaignWeekTarget.objects.get(campaign_system=self.system)
        self.assertEqual(
            row.metric, CampaignWeekTarget.Metric.STRUCTURES_REPORTED
        )
        self.assertEqual(row.target, DEFAULT_STRUCTURES_REPORTED_TARGET)
        self.assertTrue(row.proposed)

    def test_strategic_fw_objective_does_not_get_structures_reported(self):
        self.system.is_fw_objective = True
        self.system.goal = SystemGoal.TAKE
        self.system.save(update_fields=["is_fw_objective", "goal"])
        CampaignSystemSnapshot.objects.create(
            campaign_system=self.system,
            captured_at=timezone.now(),
            victory_points=900,
            victory_points_threshold=3000,
            contested_percent=30.0,
            operational_state=OperationalState.FRONTLINE,
        )
        plan.propose_week(self.campaign)
        metrics = set(
            CampaignWeekTarget.objects.filter(
                campaign_system=self.system
            ).values_list("metric", flat=True)
        )
        self.assertIn(CampaignWeekTarget.Metric.VICTORY_POINTS, metrics)
        self.assertNotIn(
            CampaignWeekTarget.Metric.STRUCTURES_REPORTED, metrics
        )

    def test_recon_goal_gets_structures_reported_target(self):
        self.system.is_fw_objective = True
        self.system.goal = SystemGoal.RECON
        self.system.save(update_fields=["is_fw_objective", "goal"])
        plan.propose_week(self.campaign)
        row = CampaignWeekTarget.objects.get(campaign_system=self.system)
        self.assertEqual(
            row.metric, CampaignWeekTarget.Metric.STRUCTURES_REPORTED
        )
        self.assertEqual(row.target, DEFAULT_STRUCTURES_REPORTED_TARGET)

    def test_faction_warfare_does_not_get_structures_reported(self):
        campaign = make_campaign(slug="fw-only", short_code="FWO")
        system = campaign.systems.first()
        CampaignSystemSnapshot.objects.create(
            campaign_system=system,
            captured_at=timezone.now(),
            victory_points=900,
            victory_points_threshold=3000,
            contested_percent=30.0,
            operational_state=OperationalState.FRONTLINE,
        )
        plan.propose_week(campaign)
        metrics = set(
            CampaignWeekTarget.objects.filter(
                campaign_system=system
            ).values_list("metric", flat=True)
        )
        self.assertNotIn(
            CampaignWeekTarget.Metric.STRUCTURES_REPORTED, metrics
        )

    def test_progress_counts_structures_reported_this_week(self):
        plan.propose_week(self.campaign)
        CampaignStructure.objects.create(
            campaign=self.campaign,
            name="Enemy Fort",
            structure_type="fortizar",
            solar_system_id=self.system.solar_system_id,
            system_name=self.system.name,
            status=StructureStatus.ANCHORED,
            source=StructureSource.RECON,
        )
        plan.update_week_progress(self.campaign)
        row = CampaignWeekTarget.objects.get(
            campaign_system=self.system,
            metric=CampaignWeekTarget.Metric.STRUCTURES_REPORTED,
        )
        self.assertEqual(row.progress, 1.0)
