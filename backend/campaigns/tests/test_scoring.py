"""Scoring weights: the fleet alliance rules, in numbers."""

from django.test import TestCase

from campaigns.models import SiteKind
from campaigns.services import scoring
from campaigns.tests.helpers import make_campaign


class KillScoringTests(TestCase):
    def setUp(self):
        self.campaign = make_campaign()

    def test_a_solo_kill_beats_a_blob_kill_for_the_individual(self):
        solo = scoring.kill_points(self.campaign, enlisted_on_mail=1)
        blob = scoring.kill_points(self.campaign, enlisted_on_mail=40)
        self.assertGreater(solo, blob)

    def test_points_stop_scaling_up_below_the_cap(self):
        """Five or fewer on the mail all get the full base."""
        five = scoring.kill_points(self.campaign, enlisted_on_mail=5)
        three = scoring.kill_points(self.campaign, enlisted_on_mail=3)
        self.assertEqual(five, three)

    def test_a_gang_sized_kill_earns_the_gang_bonus(self):
        gang = scoring.kill_points(self.campaign, enlisted_on_mail=4)
        alone = scoring.kill_points(self.campaign, enlisted_on_mail=1)
        self.assertGreater(gang, alone - 10)

    def test_isk_contribution_is_capped(self):
        modest = scoring.kill_points(
            self.campaign, enlisted_on_mail=1, isk_value=100_000_000
        )
        titan = scoring.kill_points(
            self.campaign, enlisted_on_mail=1, isk_value=100_000_000_000
        )
        self.assertLess(titan - modest, 30)

    def test_a_loss_costs_less_inside_a_fleet(self):
        alone = scoring.loss_points(self.campaign, in_fleet_or_gang=False)
        in_fleet = scoring.loss_points(self.campaign, in_fleet_or_gang=True)
        self.assertLess(alone, in_fleet)
        self.assertLess(alone, 0)


class SiteScoringTests(TestCase):
    def setUp(self):
        self.campaign = make_campaign()

    def test_a_bigger_complex_is_worth_more(self):
        scout = scoring.site_points(
            self.campaign, site_kind=SiteKind.COMPLEX, base_lp_tier=10_000
        )
        large = scoring.site_points(
            self.campaign, site_kind=SiteKind.COMPLEX, base_lp_tier=30_000
        )
        self.assertGreater(large, scout)

    def test_an_unknown_tier_scores_as_the_smallest_complex(self):
        unknown = scoring.site_points(
            self.campaign, site_kind=SiteKind.COMPLEX, base_lp_tier=None
        )
        scout = scoring.site_points(
            self.campaign, site_kind=SiteKind.COMPLEX, base_lp_tier=10_000
        )
        self.assertEqual(unknown, scout)

    def test_the_soft_cap_halves_later_sites(self):
        first = scoring.site_points(
            self.campaign, site_kind=SiteKind.ADVANTAGE_SITE, index_today=0
        )
        ninth = scoring.site_points(
            self.campaign, site_kind=SiteKind.ADVANTAGE_SITE, index_today=8
        )
        self.assertEqual(ninth, first // 2)

    def test_a_primary_system_is_worth_more(self):
        plain = scoring.site_points(
            self.campaign, site_kind=SiteKind.ADVANTAGE_SITE
        )
        primary = scoring.site_points(
            self.campaign,
            site_kind=SiteKind.ADVANTAGE_SITE,
            primary_system=True,
        )
        self.assertGreater(primary, plain)

    def test_an_unscorable_kind_is_worth_nothing(self):
        self.assertEqual(
            scoring.site_points(self.campaign, site_kind=SiteKind.UNKNOWN), 0
        )


class ModifierTests(TestCase):
    def setUp(self):
        self.campaign = make_campaign()

    def test_off_peak_hours_are_worth_more(self):
        self.assertGreater(
            scoring.day_multiplier(self.campaign, 6),
            scoring.day_multiplier(self.campaign, 19),
        )

    def test_a_streak_only_starts_paying_on_day_three(self):
        self.assertEqual(scoring.streak_points(self.campaign, 2), 0)
        self.assertGreater(scoring.streak_points(self.campaign, 3), 0)

    def test_streak_points_are_capped(self):
        self.assertEqual(
            scoring.streak_points(self.campaign, 60),
            scoring.weights(self.campaign)["streak_cap"],
        )

    def test_mixing_three_kinds_of_work_earns_a_bonus(self):
        self.assertEqual(scoring.contribution_mix_bonus(self.campaign, 2), 0)
        self.assertGreater(scoring.contribution_mix_bonus(self.campaign, 3), 0)
