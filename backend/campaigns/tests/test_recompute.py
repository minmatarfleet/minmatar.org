"""Boards are recomputed from source, so removals have to land too."""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from campaigns.helpers import campaign_day
from campaigns.models import (
    CampaignAward,
    CampaignComplexCompletion,
    CampaignEvent,
    CampaignKillmail,
    CampaignParticipantDay,
    CampaignParticipantStat,
    CampaignSiteCompletion,
    CampaignSystemSnapshot,
    OperationalState,
    SiteKind,
)
from campaigns.services import awards, sites, stats
from campaigns.services.attribution import attribute_feed_killmail
from campaigns.tests.helpers import (
    enlist,
    make_campaign,
    make_feed_killmail,
)
from eveonline.models import EveCharacterFwLpPayout, FwPayoutEventCode


class RecomputeTests(TestCase):
    def setUp(self):
        self.campaign = make_campaign()
        self.user, _ = enlist(self.campaign, "pilot", 8001)
        self.today = campaign_day()

    def test_a_withdrawn_kill_takes_its_points_with_it(self):
        feed_killmail = make_feed_killmail(
            801, victim_character_id=9999, attacker_ids=[8001]
        )
        attribute_feed_killmail(feed_killmail)
        stats.materialise_day(self.campaign, self.today)

        row = CampaignParticipantDay.objects.get(
            campaign=self.campaign, user=self.user, day=self.today
        )
        self.assertEqual(row.kills, 1)
        self.assertGreater(row.points, 0)

        # A sweep re-resolves the mail away: a character changed hands, or
        # the outcome turned out to be an awox.
        CampaignKillmail.objects.all().delete()
        stats.materialise_day(self.campaign, self.today)

        row.refresh_from_db()
        self.assertEqual(row.kills, 0)
        self.assertEqual(row.points, 0)
        self.assertFalse(row.active)

    def test_a_pod_loss_is_not_scored_and_is_not_an_active_day(self):
        """The ship loss already cost the pilot; the pod must not again."""
        feed_killmail = make_feed_killmail(
            803,
            victim_character_id=8001,
            attacker_ids=[9999],
            ship_type_id=670,
        )
        attribute_feed_killmail(feed_killmail)
        stats.materialise_day(self.campaign, self.today)

        self.assertFalse(
            CampaignParticipantDay.objects.filter(
                campaign=self.campaign, user=self.user, active=True
            ).exists()
        )


class UnconfirmedCodeTests(TestCase):
    """An unconfirmed event code is shown but must never move a standing."""

    def setUp(self):
        sites.seed_event_codes()
        self.campaign = make_campaign()
        self.user, self.character = enlist(self.campaign, "pilot", 8101)
        self.system = self.campaign.systems.first()

    def _payout(self, event_code, amount, notification_id):
        return EveCharacterFwLpPayout.objects.create(
            character=self.character,
            notification_id=notification_id,
            notification_type="FacWarLPPayoutEvent",
            occurred_at=timezone.now(),
            amount_lp=amount,
            event_code=event_code,
            location_id=self.system.solar_system_id,
        )

    def test_an_unconfirmed_advantage_site_earns_nothing(self):
        sites.attribute_payouts([self._payout(516, 10_000, 1)])
        completion = CampaignSiteCompletion.objects.get()
        self.assertFalse(completion.scored)

        stats.materialise_day(self.campaign, campaign_day())
        self.assertFalse(
            CampaignParticipantDay.objects.filter(
                campaign=self.campaign, points__gt=0
            ).exists()
        )

    def test_confirming_the_code_makes_it_count(self):
        FwPayoutEventCode.objects.filter(event_code=516).update(confirmed=True)
        sites.attribute_payouts([self._payout(516, 10_000, 2)])

        completion = CampaignSiteCompletion.objects.get()
        self.assertTrue(completion.scored)

        stats.materialise_day(self.campaign, campaign_day())
        row = CampaignParticipantDay.objects.get(campaign=self.campaign)
        self.assertGreater(row.points, 0)
        self.assertEqual(row.advantage_sites, 1)

    def test_the_stat_bar_ignores_unconfirmed_completions(self):
        sites.attribute_payouts([self._payout(516, 10_000, 3)])
        totals = stats.campaign_totals(self.campaign)
        self.assertEqual(totals["advantage_sites"], 0)
        self.assertEqual(totals["advantage_generated"], 0)


class LatePayoutTests(TestCase):
    """Pilots in one plex are polled at different times."""

    def setUp(self):
        sites.seed_event_codes()
        self.campaign = make_campaign()
        self.user_one, self.char_one = enlist(self.campaign, "one", 8201)
        self.user_two, self.char_two = enlist(self.campaign, "two", 8202)
        self.system = self.campaign.systems.first()
        self.moment = timezone.now() - timedelta(minutes=30)

        CampaignSystemSnapshot.objects.create(
            campaign_system=self.system,
            captured_at=self.moment - timedelta(minutes=5),
            victory_points=1500,
            victory_points_threshold=3000,
            contested_percent=50.0,
            operational_state=OperationalState.FRONTLINE,
        )

    def _payout(self, character, notification_id):
        # A 15,000 base plex at 50% contest on a frontline, split two ways.
        return EveCharacterFwLpPayout.objects.create(
            character=character,
            notification_id=notification_id,
            notification_type="FacWarLPPayoutEvent",
            occurred_at=self.moment,
            amount_lp=5_625,
            event_code=371,
            location_id=self.system.solar_system_id,
            ref_id=44_444,
        )

    def test_a_second_pilots_payout_joins_the_same_complex(self):
        """One plex, two pilots, two polls, still one complex.

        With only one payout in hand the inference already deduces a second
        pilot was inside, because 5,625 LP fits no tier on its own. What the
        late payout must not do is create a second complex, or leave the
        first one recorded as a solo capture.
        """
        sites.attribute_payouts([self._payout(self.char_one, 11)])
        sites.build_complex_completions(since_hours=6)

        completion = CampaignComplexCompletion.objects.get()
        self.assertEqual(completion.base_lp_tier, 15_000)
        first_payout_count = CampaignSiteCompletion.objects.filter(
            complex=completion
        ).count()
        self.assertEqual(first_payout_count, 1)

        # The other pilot's notification lands on the next poll.
        sites.attribute_payouts([self._payout(self.char_two, 12)])
        sites.build_complex_completions(since_hours=6)

        self.assertEqual(CampaignComplexCompletion.objects.count(), 1)
        completion.refresh_from_db()
        self.assertEqual(completion.split_count, 2)
        self.assertEqual(completion.base_lp_tier, 15_000)
        self.assertEqual(
            CampaignSiteCompletion.objects.filter(
                complex=completion, site_kind=SiteKind.COMPLEX
            ).count(),
            2,
        )


class AwardTests(TestCase):
    """Something to win every week, not only at the end."""

    def setUp(self):
        self.campaign = make_campaign()
        self.hunter, _ = enlist(self.campaign, "hunter", 8301)
        self.plexer, _ = enlist(self.campaign, "plexer", 8302)
        self.week_start = campaign_day() - timedelta(
            days=(campaign_day().weekday() - 3) % 7
        )

        CampaignParticipantDay.objects.create(
            campaign=self.campaign,
            user=self.hunter,
            day=self.week_start,
            kills=12,
            points=200,
            active=True,
        )
        CampaignParticipantDay.objects.create(
            campaign=self.campaign,
            user=self.plexer,
            day=self.week_start,
            complexes=9,
            points=150,
            active=True,
        )

    def test_the_week_picks_a_winner_per_award(self):
        awarded = awards.close_week(self.campaign, self.week_start)
        self.assertGreaterEqual(awarded, 2)

        top_gun = CampaignAward.objects.get(
            campaign=self.campaign, code="top_gun"
        )
        self.assertEqual(top_gun.user_id, self.hunter.id)

        marathon = CampaignAward.objects.get(
            campaign=self.campaign, code="plex_marathon"
        )
        self.assertEqual(marathon.user_id, self.plexer.id)

    def test_nobody_wins_an_award_on_zero(self):
        awards.close_week(self.campaign, self.week_start)
        self.assertFalse(
            CampaignAward.objects.filter(
                campaign=self.campaign, code="iron_wall"
            ).exists()
        )

    def test_closing_the_week_twice_awards_once(self):
        awards.close_week(self.campaign, self.week_start)
        before = CampaignAward.objects.count()
        awards.close_week(self.campaign, self.week_start)
        self.assertEqual(CampaignAward.objects.count(), before)

    def test_a_win_is_announced_on_the_timeline(self):
        awards.close_week(self.campaign, self.week_start)
        self.assertTrue(
            CampaignEvent.objects.filter(
                campaign=self.campaign, kind=CampaignEvent.Kind.AWARD
            ).exists()
        )

    def test_campaign_awards_are_decided_from_the_roll_ups(self):
        stats.rebuild_stats(self.campaign)
        self.assertGreaterEqual(awards.close_campaign(self.campaign), 1)
        warlord = CampaignAward.objects.get(
            campaign=self.campaign, code="warlord"
        )
        self.assertEqual(warlord.user_id, self.hunter.id)


class StreakTests(TestCase):
    """A streak survives the day it is still in, and nothing else."""

    def setUp(self):
        self.campaign = make_campaign()
        self.user, _ = enlist(self.campaign, "regular", 8401)
        self.today = campaign_day()

    def _active(self, *offsets):
        for offset in offsets:
            CampaignParticipantDay.objects.create(
                campaign=self.campaign,
                user=self.user,
                day=self.today - timedelta(days=offset),
                kills=1,
                points=10,
                active=True,
            )
        stats.rebuild_stats(self.campaign)
        return CampaignParticipantStat.objects.get(
            campaign=self.campaign, user=self.user
        )

    def test_consecutive_days_build_a_streak(self):
        stat = self._active(0, 1, 2)
        self.assertEqual(stat.streak_days, 3)

    def test_a_gap_breaks_it(self):
        stat = self._active(0, 2, 3)
        self.assertEqual(stat.streak_days, 1)
        self.assertEqual(stat.best_streak_days, 2)

    def test_flying_last_night_keeps_the_streak_alive(self):
        """The campaign day does not roll over until 11:00 UTC."""
        stat = self._active(1, 2)
        self.assertEqual(stat.streak_days, 2)

    def test_an_old_streak_is_over_but_still_the_best(self):
        stat = self._active(5, 6, 7, 8)
        self.assertEqual(stat.streak_days, 0)
        self.assertEqual(stat.best_streak_days, 4)

    def test_no_activity_is_no_streak(self):
        stats.rebuild_stats(self.campaign)
        self.assertFalse(
            CampaignParticipantStat.objects.filter(
                campaign=self.campaign, streak_days__gt=0
            ).exists()
        )
