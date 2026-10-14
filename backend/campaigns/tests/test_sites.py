"""LP payouts: parsing, classification and complex-class inference."""

from django.test import TestCase
from django.utils import timezone

from campaigns.models import SiteKind
from campaigns.services.sites import (
    classify_payout,
    infer_complex_class,
    parse_payout_text,
    seed_event_codes,
)
from campaigns.tests.helpers import enlist, make_campaign
from eveonline.models import EveCharacterFwLpPayout, FwPayoutEventCode

# Verbatim from a live pull on 18 Sep YC128.
COMPLEX_TEXT = """amount: 265
charRefID: 634915984
corpID: 1000182
event: 371
itemRefID: 40009123
locationID: 30002541
"""

ADVANTAGE_TEXT = """amount: 10000
charRefID: null
corpID: 1000182
event: 516
itemRefID: null
locationID: 30003069
"""


class PayoutParsingTests(TestCase):
    def test_parses_the_notification_body(self):
        fields = parse_payout_text(COMPLEX_TEXT)
        self.assertEqual(fields["amount"], 265)
        self.assertEqual(fields["event"], 371)
        self.assertEqual(fields["locationID"], 30002541)
        self.assertEqual(fields["itemRefID"], 40009123)

    def test_null_fields_become_none(self):
        fields = parse_payout_text(ADVANTAGE_TEXT)
        self.assertIsNone(fields["charRefID"])
        self.assertIsNone(fields["itemRefID"])
        self.assertEqual(fields["amount"], 10000)


class ClassificationTests(TestCase):
    def setUp(self):
        seed_event_codes()
        self.campaign = make_campaign()
        _, self.character = enlist(self.campaign, "pilot", 2001)

    def _payout(self, event_code, amount, notification_id=1):
        return EveCharacterFwLpPayout.objects.create(
            character=self.character,
            notification_id=notification_id,
            notification_type="FacWarLPPayoutEvent",
            occurred_at=timezone.now(),
            amount_lp=amount,
            event_code=event_code,
            location_id=30003069,
        )

    def test_complex_code_is_confirmed_and_scorable(self):
        kind, scorable = classify_payout(self._payout(371, 265))
        self.assertEqual(kind, SiteKind.COMPLEX)
        self.assertTrue(scorable)

    def test_advantage_family_splits_on_the_amount(self):
        kind, _ = classify_payout(self._payout(516, 10_000, 2))
        self.assertEqual(kind, SiteKind.ADVANTAGE_SITE)

        kind, _ = classify_payout(self._payout(516, 15_000, 3))
        self.assertEqual(kind, SiteKind.SUPPLY_CACHE)

    def test_unconfirmed_code_is_stored_but_never_scored(self):
        """Event 359 is a candidate battlefield, not a confirmed one."""
        _, scorable = classify_payout(self._payout(359, 52_500, 4))
        self.assertFalse(scorable)

    def test_unknown_code_is_unknown_and_not_scored(self):
        kind, scorable = classify_payout(self._payout(999, 1_234, 5))
        self.assertEqual(kind, SiteKind.UNKNOWN)
        self.assertFalse(scorable)

    def test_seeding_never_overwrites_a_human_confirmation(self):
        FwPayoutEventCode.objects.filter(event_code=359).update(
            confirmed=True, site_kind=SiteKind.BATTLEFIELD
        )
        seed_event_codes()
        row = FwPayoutEventCode.objects.get(event_code=359)
        self.assertTrue(row.confirmed)
        self.assertEqual(row.site_kind, SiteKind.BATTLEFIELD)


class ComplexInferenceTests(TestCase):
    """base = amount x pilots / (state x contested x suppression)."""

    def test_recovers_a_unique_tier_with_high_confidence(self):
        """17,500 is the one tier no other tier is a multiple of.

        17500 x 1.5 x 0.5 = 13125 solo. Two pilots would imply 35,000 and
        three 52,500, neither of which is a tier, so the reading is certain.
        """
        result = infer_complex_class(
            amount_lp=13_125,
            split_count=1,
            operational_state="frontline",
            contested=0.5,
            suppression=1.0,
        )
        self.assertEqual(result["base_lp_tier"], 17_500)
        self.assertEqual(result["candidates"], ["Small ADV-1"])
        self.assertEqual(result["alternate_tiers"], [])
        self.assertEqual(result["confidence"], "high")

    def test_a_tier_that_is_a_multiple_of_another_is_never_certain(self):
        """A solo 15,000 plex and a shared 30,000 plex pay the same."""
        result = infer_complex_class(
            amount_lp=11_250,
            split_count=1,
            operational_state="frontline",
            contested=0.5,
            suppression=1.0,
        )
        self.assertEqual(result["base_lp_tier"], 15_000)
        self.assertEqual(result["confidence"], "low")
        self.assertIn(30_000, result["alternate_tiers"])

    def test_a_shared_tier_reports_every_candidate(self):
        """25,000 is one base shared by four different complex classes."""
        result = infer_complex_class(
            amount_lp=18_750,
            split_count=1,
            operational_state="frontline",
            contested=0.5,
            suppression=1.0,
        )
        self.assertEqual(result["base_lp_tier"], 25_000)
        self.assertGreater(len(result["candidates"]), 1)
        self.assertIn("Medium ADV-1", result["candidates"])
        self.assertEqual(result["confidence"], "low")

    def test_split_between_pilots_is_recovered(self):
        # Same 15,000 plex split three ways.
        result = infer_complex_class(
            amount_lp=3_750,
            split_count=3,
            operational_state="frontline",
            contested=0.5,
            suppression=1.0,
        )
        self.assertEqual(result["base_lp_tier"], 15_000)

    def test_untracked_pilots_inside_are_tried(self):
        """Our split count is a lower bound; someone untracked was in there.

        3,750 LP fits a 10,000 plex shared with one untracked pilot and a
        15,000 plex shared with two. We take the smaller split as the primary
        reading, list both, and never call it high confidence.
        """
        result = infer_complex_class(
            amount_lp=3_750,
            split_count=1,
            operational_state="frontline",
            contested=0.5,
            suppression=1.0,
        )
        self.assertEqual(result["base_lp_tier"], 10_000)
        self.assertEqual(result["split_used"], 2)
        self.assertEqual(result["confidence"], "low")
        self.assertIn(15_000, result["alternate_tiers"])

    def test_suppression_is_divided_out(self):
        # Stage 4 suppression adds 15%.
        result = infer_complex_class(
            amount_lp=int(11_250 * 1.15),
            split_count=1,
            operational_state="frontline",
            contested=0.5,
            suppression=1.15,
        )
        self.assertEqual(result["base_lp_tier"], 15_000)

    def test_rearguard_multiplier_is_handled(self):
        result = infer_complex_class(
            amount_lp=75,
            split_count=1,
            operational_state="rearguard",
            contested=0.5,
            suppression=1.0,
        )
        self.assertEqual(result["base_lp_tier"], 15_000)

    def test_nothing_that_fits_is_reported_as_unknown(self):
        result = infer_complex_class(
            amount_lp=7,
            split_count=1,
            operational_state="unknown",
            contested=1.0,
            suppression=1.0,
        )
        self.assertIsNone(result["base_lp_tier"])
        self.assertEqual(result["confidence"], "unknown")


class InferenceInputConfidenceTests(TestCase):
    """A recovered tier is only certain when its inputs were measured."""

    def test_unmeasured_inputs_can_never_be_high_confidence(self):
        # 22,500 LP with no snapshot: state and contest both fall back to 1.0,
        # which happens to land exactly on the 45,000 elite tier at a split of
        # two. The tier is worth storing; calling it certain would be a lie.
        result = infer_complex_class(
            amount_lp=22_500,
            split_count=1,
            operational_state="unknown",
            contested=1.0,
            suppression=1.0,
            inputs_measured=False,
        )
        self.assertEqual(result["base_lp_tier"], 45_000)
        self.assertEqual(result["confidence"], "low")

    def test_the_same_reading_with_measured_inputs_is_certain(self):
        result = infer_complex_class(
            amount_lp=13_125,
            split_count=1,
            operational_state="frontline",
            contested=0.5,
            suppression=1.0,
            inputs_measured=True,
        )
        self.assertEqual(result["confidence"], "high")

    def test_a_very_low_contest_reading_is_not_certain_either(self):
        result = infer_complex_class(
            amount_lp=262,
            split_count=1,
            operational_state="frontline",
            contested=0.01,
            suppression=1.0,
        )
        self.assertNotEqual(result["confidence"], "high")
