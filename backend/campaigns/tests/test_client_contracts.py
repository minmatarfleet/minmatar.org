"""Campaign payloads the desktop window and the website render (app/contracts.py).

The desktop's Campaigns window reads /api/campaigns/overlay; the website's
objectives table reads the week plan's objective_rows and the systems. One
made-up campaign covers capture, defend, a flip, gain and destroy advantage,
structure reports and a system with no readings yet.
"""

from datetime import timedelta

from django.core.cache import cache
from django.test import Client, TestCase

from app import contracts
from campaigns.helpers import campaign_week_start
from campaigns.models import (
    CampaignAdvantageReading,
    CampaignAdvantageState,
    CampaignKillmail,
    CampaignKillmailParticipant,
    CampaignSystem,
    CampaignSystemSnapshot,
    CampaignWeekTarget,
    KillmailOutcome,
    SystemGoal,
    SystemPriority,
)
from campaigns.tests.helpers import auth_headers, enlist, grant, make_campaign
from eveonline.models import EveCharacter, EvePlayer

AMARR, MINMATAR = 500003, 500002
Metric = CampaignWeekTarget.Metric
# What the website's objectives table reads from each system summary.
SYSTEM_KEYS = (
    "id",
    "name",
    "solar_system_id",
    "goal",
    "priority",
    "is_fw_objective",
    "status_chip",
    "occupier_faction_id",
    "owner_faction_id",
    "contested_percent",
    "contested_change_24h",
    "victory_points",
    "victory_points_threshold",
    "advantage_our_pct",
    "advantage_enemy_pct",
)
# Hours before FIXED_NOW (Saturday 18:00) that fall before the week opened
# (Thursday 11:00).
BEFORE_THE_WEEK = 60


class CampaignContractTests(TestCase):
    def setUp(self):
        cache.clear()
        self.clock = contracts.frozen_clock()
        self.clock.start()
        self.addCleanup(self.clock.stop)
        self.now = contracts.FIXED_NOW
        self.campaign = make_campaign(slug="contract-push", name="Push")
        self.user, character = enlist(self.campaign, "pilot", 3001)
        main = EveCharacter.objects.create(
            character_id=3002, character_name="Pilot Main", user=self.user
        )
        EvePlayer.objects.create(
            user=self.user, nickname="pilot", primary_character=main
        )
        grant(self.user, "view_campaign")
        self.character = character
        self.systems = {}
        self.campaign.systems.all().delete()

    def _system(self, pk, solar_system_id, name, goal, priority, fw=True):
        self.systems[name] = CampaignSystem.objects.create(
            id=pk,
            campaign=self.campaign,
            solar_system_id=solar_system_id,
            name=name,
            goal=goal,
            priority=priority,
            is_fw_objective=fw,
        )
        return self.systems[name]

    def _snapshot(self, system, hours_ago, vp, occupier):
        CampaignSystemSnapshot.objects.create(
            campaign_system=system,
            captured_at=self.now - timedelta(hours=hours_ago),
            victory_points=vp,
            victory_points_threshold=3000,
            contested_percent=vp / 3000 * 100,
            occupier_faction_id=occupier,
            owner_faction_id=occupier,
        )

    def _target(self, pk, system, metric, **fields):
        CampaignWeekTarget.objects.create(
            id=pk,
            campaign_system=system,
            week_start=campaign_week_start(),
            metric=metric,
            **fields,
        )

    def _advantage(self, system, our, enemy, our_day_ago, enemy_day_ago):
        CampaignAdvantageState.objects.create(
            campaign_system=system,
            our_pct=our,
            enemy_pct=enemy,
            basis="reading",
        )
        CampaignAdvantageReading.objects.create(
            campaign_system=system,
            reported_at=self.now - timedelta(hours=25),
            our_pct=our_day_ago,
            enemy_pct=enemy_day_ago,
        )

    def _contested_systems(self):
        kamela = self._system(
            101, 30003069, "Kamela", SystemGoal.TAKE, SystemPriority.MEDIUM
        )
        kourmonen = self._system(
            102, 30003068, "Kourmonen", SystemGoal.HOLD, SystemPriority.HIGH
        )
        huola = self._system(
            103, 30003067, "Huola", SystemGoal.TAKE, SystemPriority.MEDIUM
        )
        self._snapshot(kamela, BEFORE_THE_WEEK, 900, AMARR)
        self._snapshot(kamela, 25, 1620, AMARR)
        self._snapshot(kamela, 0, 1860, AMARR)
        self._snapshot(kourmonen, BEFORE_THE_WEEK, 600, MINMATAR)
        self._snapshot(kourmonen, 25, 300, MINMATAR)
        self._snapshot(kourmonen, 0, 390, MINMATAR)
        # Changed hands this week: ours now.
        self._snapshot(huola, BEFORE_THE_WEEK, 2700, AMARR)
        self._snapshot(huola, 25, 2850, AMARR)
        self._snapshot(huola, 0, 300, MINMATAR)
        return kamela, kourmonen, huola

    def _seed_targets(self):
        kamela, kourmonen, huola = self._contested_systems()
        arzad = self._system(
            104, 30003504, "Arzad", SystemGoal.HOLD, SystemPriority.LOW
        )
        sosala = self._system(
            105, 30003070, "Sosala", SystemGoal.TAKE, SystemPriority.MEDIUM
        )
        bosboger = self._system(
            106,
            30003071,
            "Bosboger",
            SystemGoal.RECON,
            SystemPriority.LOW,
            fw=False,
        )
        vard = self._system(
            107, 30003072, "Vard", SystemGoal.TAKE, SystemPriority.MEDIUM
        )
        self._advantage(arzad, 41, 30, 47, 30)
        self._advantage(sosala, 20, 35, 20, 50)
        # Behind, on pace and ahead, so the order shows losing first.
        self._target(
            201,
            kamela,
            Metric.VICTORY_POINTS,
            target=900,
            progress=100,
            pace_expected=500,
        )
        self._target(202, kamela, Metric.ADVANTAGE_GAIN, target=60)
        self._target(
            203, kourmonen, Metric.DAYS_UNDER_LINE, target=7, progress=2
        )
        self._target(
            204,
            huola,
            Metric.VICTORY_POINTS,
            target=900,
            progress=2000,
            pace_expected=1000,
        )
        self._target(
            205,
            arzad,
            Metric.ADVANTAGE_MAINTAIN,
            target=40,
            baseline=30,
            progress=41,
            pace_expected=40,
        )
        self._target(
            206,
            sosala,
            Metric.ADVANTAGE_DESTROY,
            target=20,
            baseline=60,
            progress=35,
            pace_expected=50,
        )
        self._target(
            207,
            bosboger,
            Metric.STRUCTURES_REPORTED,
            target=3,
            progress=1,
            proposed=False,
        )
        self._target(208, vard, Metric.VICTORY_POINTS, target=900)

    def _seed_pilot_activity(self):
        mail = CampaignKillmail.objects.create(
            campaign=self.campaign,
            killmail_id=9000001,
            killmail_time=self.now - timedelta(minutes=10),
            solar_system_id=30003069,
            outcome=KillmailOutcome.KILL,
        )
        CampaignKillmailParticipant.objects.create(
            killmail=mail,
            character_id=self.character.character_id,
            character_name=self.character.character_name,
            user=self.user,
            enlisted=True,
            role="attacker",
        )

    def _get(self, url):
        response = Client().get(url, **auth_headers(self.user))
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def _web_payload(self):
        slug = self.campaign.slug
        detail = self._get(f"/api/campaigns/{slug}")
        return {
            "systems": [
                {key: system[key] for key in SYSTEM_KEYS}
                for system in detail["systems"]
            ],
            "week": self._get(f"/api/campaigns/{slug}/week"),
        }

    def test_campaign_overlay(self):
        self._seed_targets()
        self._seed_pilot_activity()
        contracts.check(
            self,
            contracts.DESKTOP / "campaign_overlay.json",
            self._get("/api/campaigns/overlay"),
        )

    def test_campaign_week(self):
        self._seed_targets()
        contracts.check(
            self, contracts.WEB / "campaign_week.json", self._web_payload()
        )

    def test_campaign_week_before_targets(self):
        self._contested_systems()
        contracts.check(
            self,
            contracts.WEB / "campaign_week_no_targets.json",
            self._web_payload(),
        )
