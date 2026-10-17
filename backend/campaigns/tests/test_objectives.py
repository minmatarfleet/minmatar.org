"""The week's objective rows, shared by the website and the desktop window."""

from datetime import timedelta

from django.core.cache import cache
from django.test import Client, TestCase
from django.utils import timezone

from campaigns.helpers import campaign_week_start
from campaigns.models import (
    CampaignSystem,
    CampaignSystemSnapshot,
    CampaignWeekTarget,
    SystemGoal,
    SystemPriority,
)
from campaigns.services import objectives
from campaigns.tests.helpers import (
    KAMELA,
    KOURMONEN,
    auth_headers,
    enlist,
    grant,
    make_campaign,
)

AMARR, MINMATAR = 500003, 500002
HUOLA, ARZAD = 30003067, 30003504


class WeeklyRowsTests(TestCase):
    def setUp(self):
        cache.clear()
        self.now = timezone.now()
        self.campaign = make_campaign()
        self.kamela = self.campaign.systems.get(solar_system_id=KAMELA)
        self.kourmonen = self._system(KOURMONEN, "Kourmonen", SystemGoal.HOLD)
        self.huola = self._system(HUOLA, "Huola", SystemGoal.TAKE)
        self.user, _ = enlist(self.campaign, "pilot", 3001)
        grant(self.user, "view_campaign")

    def _system(self, solar_system_id, name, goal, priority="medium"):
        return CampaignSystem.objects.create(
            campaign=self.campaign,
            solar_system_id=solar_system_id,
            name=name,
            goal=goal,
            priority=priority,
        )

    def _snapshot(self, system, vp, occupier=AMARR, hours_ago=0):
        CampaignSystemSnapshot.objects.create(
            campaign_system=system,
            captured_at=self.now - timedelta(hours=hours_ago),
            victory_points=vp,
            victory_points_threshold=3000,
            contested_percent=vp / 3000 * 100,
            occupier_faction_id=occupier,
            owner_faction_id=occupier,
        )

    def _target(self, system, metric, progress=0.0, pace_expected=0.0):
        return CampaignWeekTarget.objects.create(
            campaign_system=system,
            week_start=campaign_week_start(),
            metric=metric,
            target=10,
            progress=progress,
            pace_expected=pace_expected,
        )

    def test_within_a_priority_the_losing_objectives_come_first(self):
        vp = CampaignWeekTarget.Metric.VICTORY_POINTS
        # Kamela ahead, Huola behind, Kourmonen on pace; all medium.
        self._target(self.kamela, vp, progress=10, pace_expected=5)
        self._target(self.huola, vp, progress=1, pace_expected=5)
        self._target(
            self.kourmonen,
            CampaignWeekTarget.Metric.DAYS_UNDER_LINE,
            progress=5,
            pace_expected=5,
        )
        rows = objectives.weekly_rows(self.campaign)
        self.assertEqual(
            [(row["name"], row["pace"]) for row in rows],
            [
                ("Huola", "behind"),
                ("Kourmonen", "on_pace"),
                ("Kamela", "ahead"),
            ],
        )

    def test_priority_still_leads(self):
        self.kamela.priority = SystemPriority.HIGH
        self.kamela.save()
        vp = CampaignWeekTarget.Metric.VICTORY_POINTS
        self._target(self.kamela, vp, progress=10, pace_expected=5)
        self._target(self.huola, vp, progress=1, pace_expected=5)
        rows = objectives.weekly_rows(self.campaign)
        self.assertEqual([row["name"] for row in rows], ["Kamela", "Huola"])

    def test_ties_are_by_name(self):
        vp = CampaignWeekTarget.Metric.VICTORY_POINTS
        self._target(self.kamela, vp)
        self._target(self.huola, vp)
        rows = objectives.weekly_rows(self.campaign)
        self.assertEqual([row["name"] for row in rows], ["Huola", "Kamela"])

    def test_structure_targets_measure_reports_against_the_target(self):
        target = self._target(
            self.kamela,
            CampaignWeekTarget.Metric.STRUCTURES_REPORTED,
            progress=4,
        )
        (row,) = objectives.weekly_rows(self.campaign)
        self.assertEqual(row["objective"], "report_structures")
        self.assertEqual(row["target_id"], target.id)
        self.assertEqual(row["progress_percent"], 40.0)
        self.assertEqual(row["structures_reported"], 4)

    def test_without_targets_the_hottest_contest_leads(self):
        self._snapshot(self.kamela, 300)
        self._snapshot(self.huola, 2400)
        self._snapshot(self.kourmonen, 900, occupier=MINMATAR)
        rows = objectives.weekly_rows(self.campaign)
        self.assertEqual(
            [(row["name"], row["objective"]) for row in rows],
            [
                ("Huola", "capture_complexes"),
                ("Kourmonen", "defend_complexes"),
                ("Kamela", "capture_complexes"),
            ],
        )
        self.assertTrue(all(row["target_id"] is None for row in rows))
        self.assertTrue(all(row["pace"] is None for row in rows))

    def test_a_recon_system_without_targets_reports_structures(self):
        self.kamela.goal = SystemGoal.RECON
        self.kamela.save()
        row = next(
            row
            for row in objectives.weekly_rows(self.campaign)
            if row["name"] == "Kamela"
        )
        self.assertEqual(row["objective"], "report_structures")
        self.assertIsNone(row["progress_percent"])

    def test_the_week_plan_carries_the_rows(self):
        self._snapshot(self.kamela, 1500)
        self._target(self.kamela, CampaignWeekTarget.Metric.VICTORY_POINTS)
        response = Client().get(
            f"/api/campaigns/{self.campaign.slug}/week",
            **auth_headers(self.user),
        )
        self.assertEqual(response.status_code, 200)
        (row,) = response.json()["objective_rows"]
        self.assertEqual(row["objective"], "capture_complexes")
        self.assertEqual(row["progress_percent"], 50.0)
        self.assertEqual(row["victory_points"], 1500)

    def test_the_desktop_window_reads_the_same_rows_in_the_same_order(self):
        vp = CampaignWeekTarget.Metric.VICTORY_POINTS
        self._target(self.kamela, vp, progress=10, pace_expected=5)
        self._target(self.huola, vp, progress=1, pace_expected=5)
        self._target(
            self.kourmonen, CampaignWeekTarget.Metric.STRUCTURES_REPORTED
        )
        response = Client().get(
            "/api/campaigns/overlay", **auth_headers(self.user)
        )
        names = [row["name"] for row in response.json()["campaign"]["systems"]]
        web = [
            row["name"]
            for row in objectives.weekly_rows(self.campaign)
            if row["objective"] != "report_structures"
        ]
        self.assertEqual(names, web)
        self.assertEqual(names, ["Huola", "Kamela"])
