"""The desktop app's Campaigns window: systems at a glance, who is out."""

from datetime import timedelta

from django.contrib.auth.models import User
from django.core.cache import cache
from django.db.models import signals
from django.test import Client, TestCase
from django.utils import timezone

import factory

from campaigns.helpers import campaign_week_start
from campaigns.models import (
    CampaignKillmail,
    CampaignKillmailParticipant,
    CampaignStatus,
    CampaignSystem,
    CampaignSystemSnapshot,
    CampaignWeekTarget,
    KillmailOutcome,
    SystemGoal,
    SystemPriority,
)
from campaigns.tests.helpers import (
    KAMELA,
    KOURMONEN,
    auth_headers,
    enlist,
    grant,
    make_campaign,
)
from eveonline.models import EveCharacter, EvePlayer
from fleets.models import EveFleet, EveFleetInstance, EveFleetInstanceMember

URL = "/api/campaigns/overlay"
AMARR, MINMATAR = 500003, 500002


class CampaignOverlayTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()
        self.now = timezone.now()
        self.campaign = make_campaign()
        self.kamela = self.campaign.systems.get(solar_system_id=KAMELA)
        self.kourmonen = CampaignSystem.objects.create(
            campaign=self.campaign,
            solar_system_id=KOURMONEN,
            name="Kourmonen",
            goal=SystemGoal.HOLD,
            priority=SystemPriority.HIGH,
        )
        self.user, self.character = enlist(self.campaign, "pilot", 3001)
        self.main = EveCharacter.objects.create(
            character_id=3002, character_name="Pilot Main", user=self.user
        )
        EvePlayer.objects.create(
            user=self.user, nickname="pilot", primary_character=self.main
        )
        grant(self.user, "view_campaign")

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

    def _get(self, user=None):
        response = self.client.get(URL, **auth_headers(user or self.user))
        self.assertEqual(response.status_code, 200)
        return response.json()["campaign"]

    def test_a_pilot_without_the_feature_is_refused(self):
        outsider = User.objects.create(username="outsider")
        response = self.client.get(URL, **auth_headers(outsider))
        self.assertEqual(response.status_code, 403)

    def test_a_public_campaign_still_needs_the_feature(self):
        """The window names pilots, which a public campaign page does not."""
        self.campaign.visibility = "public"
        self.campaign.save()
        outsider = User.objects.create(username="outsider")
        response = self.client.get(URL, **auth_headers(outsider))
        self.assertEqual(response.status_code, 403)

    def test_no_live_campaign_is_an_empty_window_not_an_error(self):
        self.campaign.status = CampaignStatus.COMPLETED
        self.campaign.save()
        self.assertIsNone(self._get())

    def test_the_pilots_own_campaign_wins_over_a_newer_one(self):
        make_campaign(
            slug="newer",
            short_code="NEW",
            name="Newer",
            start_at=self.now - timedelta(days=1),
        )
        self.assertEqual(self._get()["slug"], self.campaign.slug)

    def test_complex_rows_are_victory_points_with_a_24h_move(self):
        self._snapshot(self.kamela, 25, 1620, AMARR)
        self._snapshot(self.kamela, 0, 1860, AMARR)
        self._snapshot(self.kourmonen, 25, 300, MINMATAR)
        self._snapshot(self.kourmonen, 0, 390, MINMATAR)

        rows = self._get()["systems"]

        # High priority first.
        self.assertEqual(
            [row["name"] for row in rows], ["Kourmonen", "Kamela"]
        )
        defend, capture = rows

        self.assertEqual(capture["objective"], "capture_complexes")
        self.assertEqual(capture["objective_label"], "Capture complexes")
        self.assertEqual(capture["holder"], "amarr")
        self.assertEqual(capture["progress_percent"], 62.0)
        self.assertEqual(capture["change_24h"], 8.0)
        self.assertEqual(capture["detail"], "1,860 of 3,000 victory points")

        # Defending, their victory points drain the bar: 13% of the way to
        # flipping is 87% safe, and three points gained is three lost.
        self.assertEqual(defend["objective"], "defend_complexes")
        self.assertEqual(defend["holder"], "minmatar")
        self.assertEqual(defend["progress_percent"], 87.0)
        self.assertEqual(defend["change_24h"], -3.0)
        self.assertNotIn("contested_percent", defend)

    def test_a_system_with_no_readings_has_no_progress_yet(self):
        row = next(r for r in self._get()["systems"] if r["name"] == "Kamela")
        self.assertIsNone(row["progress_percent"])
        self.assertIsNone(row["change_24h"])
        self.assertIsNone(row["holder"])

    def test_this_weeks_targets_set_the_objectives(self):
        CampaignWeekTarget.objects.create(
            campaign_system=self.kamela,
            week_start=campaign_week_start(),
            metric=CampaignWeekTarget.Metric.ADVANTAGE_GAIN,
            target=75,
        )
        CampaignWeekTarget.objects.create(
            campaign_system=self.kourmonen,
            week_start=campaign_week_start(),
            metric=CampaignWeekTarget.Metric.STRUCTURES_REPORTED,
            target=3,
        )
        rows = self._get()["systems"]
        self.assertEqual(
            [(row["name"], row["objective"]) for row in rows],
            [("Kamela", "gain_advantage")],
        )

    def _kill(self, killmail_id, minutes_ago, character_id, role="attacker"):
        mail = CampaignKillmail.objects.create(
            campaign=self.campaign,
            killmail_id=killmail_id,
            killmail_time=self.now - timedelta(minutes=minutes_ago),
            solar_system_id=KAMELA,
            outcome=(
                KillmailOutcome.KILL
                if role == "attacker"
                else KillmailOutcome.LOSS
            ),
        )
        CampaignKillmailParticipant.objects.create(
            killmail=mail,
            character_id=character_id,
            character_name="Alt",
            user=EveCharacter.objects.get(character_id=character_id).user,
            enlisted=True,
            role=role,
        )

    def _fleet_member(self, character_id, minutes_ago):
        with factory.django.mute_signals(signals.pre_save, signals.post_save):
            fleet = EveFleet.objects.create(
                type="standing",
                start_time=self.now - timedelta(hours=2),
                campaign=self.campaign,
            )
        instance = EveFleetInstance.objects.create(
            id=fleet.id * 1000, eve_fleet=fleet
        )
        member = EveFleetInstanceMember.objects.create(
            eve_fleet_instance=instance,
            character_id=character_id,
            character_name="Fleet Pilot",
            role="squad_member",
            role_name="Squad Member",
            ship_type_id=621,
            ship_name="Rifter",
            solar_system_id=KOURMONEN,
            solar_system_name="Kourmonen",
            squad_id=1,
            wing_id=1,
        )
        EveFleetInstanceMember.objects.filter(pk=member.pk).update(
            updated_at=self.now - timedelta(minutes=minutes_ago)
        )

    def test_active_pilots_show_as_their_main_newest_first(self):
        self._kill(1, 40, self.character.character_id)
        self._kill(2, 30, self.character.character_id)
        self._kill(3, 90, self.character.character_id)  # over an hour ago
        _, fleet_character = enlist(self.campaign, "flyer", 4001)
        self._fleet_member(fleet_character.character_id, 5)

        pilots = self._get()["active_pilots"]

        self.assertEqual(
            [pilot["character_name"] for pilot in pilots],
            ["Flyer", "Pilot Main"],
        )
        flyer, pilot = pilots
        self.assertTrue(flyer["in_fleet"])
        self.assertEqual(flyer["system"], "Kourmonen")
        self.assertEqual(pilot["character_id"], 3002)
        self.assertEqual(pilot["kills"], 2)
        self.assertEqual(pilot["system"], "Kamela")

    def test_a_pilot_in_the_fleet_but_not_the_campaign_is_left_out(self):
        bystander = User.objects.create(username="bystander")
        EveCharacter.objects.create(
            character_id=5001, character_name="Bystander", user=bystander
        )
        self._fleet_member(5001, 5)
        self.assertEqual(self._get()["active_pilots"], [])

    def test_losses_count_as_activity(self):
        self._kill(1, 10, self.character.character_id, role="victim")
        (pilot,) = self._get()["active_pilots"]
        self.assertEqual(pilot["losses"], 1)
        self.assertEqual(pilot["kills"], 0)
