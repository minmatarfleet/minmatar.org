"""The desktop app's Campaigns window: systems at a glance, who is out."""

from datetime import timedelta

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db.models import signals
from django.test import Client, TestCase
from django.utils import timezone

import factory

from campaigns.endpoints import overlay
from campaigns.helpers import campaign_week_start
from campaigns.models import (
    Campaign,
    CampaignAdvantageReading,
    CampaignAdvantageState,
    CampaignKillmail,
    CampaignKillmailParticipant,
    CampaignSiteCompletion,
    CampaignStatus,
    CampaignSystem,
    CampaignSystemSnapshot,
    CampaignWeekTarget,
    KillmailOutcome,
    SiteKind,
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
from eveonline.models import EveCharacter, EveCharacterFwLpPayout, EvePlayer
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

    def _kill(
        self,
        killmail_id,
        minutes_ago,
        character_ids,
        role="attacker",
        outcome=None,
    ):
        mail = CampaignKillmail.objects.create(
            campaign=self.campaign,
            killmail_id=killmail_id,
            killmail_time=self.now - timedelta(minutes=minutes_ago),
            solar_system_id=KAMELA,
            outcome=outcome
            or (
                KillmailOutcome.KILL
                if role == "attacker"
                else KillmailOutcome.LOSS
            ),
        )
        if isinstance(character_ids, int):
            character_ids = [character_ids]
        for character_id in character_ids:
            CampaignKillmailParticipant.objects.create(
                killmail=mail,
                character_id=character_id,
                character_name="Alt",
                user=EveCharacter.objects.get(character_id=character_id).user,
                enlisted=True,
                role=role,
            )

    def _fleet_member(self, character_id, minutes_ago, ended_ago=None):
        with factory.django.mute_signals(signals.pre_save, signals.post_save):
            fleet = EveFleet.objects.create(
                type="standing",
                start_time=self.now - timedelta(hours=2),
                campaign=self.campaign,
            )
        instance = EveFleetInstance.objects.create(
            id=fleet.id * 1000,
            eve_fleet=fleet,
            end_time=(
                self.now - timedelta(minutes=ended_ago)
                if ended_ago is not None
                else None
            ),
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

    def test_two_characters_on_one_mail_are_one_kill(self):
        alt = EveCharacter.objects.create(
            character_id=3003, character_name="Pilot Alt", user=self.user
        )
        self._kill(1, 10, [self.character.character_id, alt.character_id])
        (pilot,) = self._get()["active_pilots"]
        self.assertEqual(pilot["kills"], 1)

    def test_shooting_at_our_own_loss_is_not_a_kill(self):
        self._kill(
            1,
            10,
            self.character.character_id,
            outcome=KillmailOutcome.LOSS,
        )
        self.assertEqual(self._get()["active_pilots"], [])

    def test_a_fleet_that_ended_before_the_hour_is_not_activity(self):
        _, flyer = enlist(self.campaign, "flyer", 4001)
        # The member row still says "seen 5 minutes ago", but its fleet
        # instance closed two hours ago.
        self._fleet_member(flyer.character_id, 5, ended_ago=120)
        self.assertEqual(self._get()["active_pilots"], [])

    def test_site_captures_count_as_activity(self):
        for notification_id, kind in (
            (1, SiteKind.COMPLEX),
            (2, SiteKind.COMPLEX),
            (3, SiteKind.ADVANTAGE_SITE),
            (4, SiteKind.KILL),
        ):
            payout = EveCharacterFwLpPayout.objects.create(
                character=self.character,
                notification_id=notification_id,
                notification_type="FacWarLPPayoutEvent",
                occurred_at=self.now - timedelta(minutes=15),
                amount_lp=10_000,
                event_code=371,
                location_id=KAMELA,
            )
            CampaignSiteCompletion.objects.create(
                campaign=self.campaign,
                payout=payout,
                user=self.user,
                character_id=self.character.character_id,
                campaign_system=self.kamela,
                occurred_at=payout.occurred_at,
                event_code=371,
                site_kind=kind,
            )
        (pilot,) = self._get()["active_pilots"]
        self.assertEqual(pilot["complexes"], 2)
        self.assertEqual(pilot["advantage_sites"], 1)
        self.assertEqual(pilot["system"], "Kamela")

    def _advantage(
        self, system, metric, our, enemy, our_day_ago, enemy_day_ago
    ):
        CampaignWeekTarget.objects.create(
            campaign_system=system,
            week_start=campaign_week_start(),
            metric=metric,
            target=75,
        )
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
        # A newer reading inside the day is not the 24h baseline.
        CampaignAdvantageReading.objects.create(
            campaign_system=system,
            reported_at=self.now - timedelta(hours=2),
            our_pct=0,
            enemy_pct=0,
        )

    def test_advantage_rows_measure_the_level_and_its_day(self):
        self._advantage(
            self.kamela,
            CampaignWeekTarget.Metric.ADVANTAGE_GAIN,
            our=41,
            enemy=30,
            our_day_ago=47,
            enemy_day_ago=30,
        )
        self._advantage(
            self.kourmonen,
            CampaignWeekTarget.Metric.ADVANTAGE_DESTROY,
            our=20,
            enemy=35,
            our_day_ago=20,
            enemy_day_ago=50,
        )
        rows = {row["name"]: row for row in self._get()["systems"]}

        gain = rows["Kamela"]
        self.assertEqual(gain["objective"], "gain_advantage")
        self.assertEqual(gain["progress_percent"], 41.0)
        self.assertEqual(gain["change_24h"], -6.0)
        self.assertEqual(gain["detail"], "Our advantage 41%")

        # Destroy reads as how far theirs has fallen: 35 left is 65 done,
        # and theirs dropping 15 is 15 gained.
        destroy = rows["Kourmonen"]
        self.assertEqual(destroy["objective"], "destroy_advantage")
        self.assertEqual(destroy["progress_percent"], 65.0)
        self.assertEqual(destroy["change_24h"], 15.0)

    def test_a_fresh_copy_is_served_without_touching_the_database(self):
        overlay.overlay(self.campaign)
        with self.assertNumQueries(0):
            overlay.overlay(self.campaign)

    def test_a_stale_copy_is_served_while_another_request_rebuilds(self):
        overlay.overlay(self.campaign)
        key = overlay.CACHE_KEY.format(campaign_id=self.campaign.id)
        stale = cache.get(key)
        cache.set(key, {**stale, "fresh_until": 0}, 600)
        cache.add(overlay.LOCK_KEY.format(campaign_id=self.campaign.id), 1, 30)
        with self.assertNumQueries(0):
            self.assertEqual(overlay.overlay(self.campaign), stale["payload"])

    def test_route_slugs_cannot_be_campaign_slugs(self):
        with self.assertRaises(ValidationError):
            Campaign(slug="overlay").clean()
