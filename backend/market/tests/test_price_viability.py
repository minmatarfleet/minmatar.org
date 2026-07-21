from django.test import SimpleTestCase

from market.helpers.price_viability import (
    DEFAULT_BASELINE_PRICE_FLOOR,
    DEFAULT_MAX_MARKUP_PCT,
    DEFAULT_PRICE_VIABILITY_POLICY,
    PriceViabilityPolicy,
    is_price_viable,
    order_quantity_counts_as_reasonable,
)


class PriceViabilityHelperTestCase(SimpleTestCase):
    def test_default_policy_constants(self):
        self.assertEqual(DEFAULT_MAX_MARKUP_PCT, 20)
        self.assertEqual(DEFAULT_BASELINE_PRICE_FLOOR, 1_000_000)
        self.assertEqual(
            DEFAULT_PRICE_VIABILITY_POLICY,
            PriceViabilityPolicy(
                max_markup_pct=20,
                baseline_price_floor=1_000_000,
            ),
        )

    def test_default_thresholds_include_boundary(self):
        self.assertTrue(is_price_viable(2_400_000, 2_000_000))
        self.assertFalse(is_price_viable(2_400_001, 2_000_000))

    def test_missing_or_invalid_baseline_is_viable(self):
        self.assertTrue(is_price_viable(1_000_000, None))
        self.assertTrue(is_price_viable(1_000_000, 0))
        self.assertTrue(is_price_viable(1_000_000, -10))

    def test_cheap_baseline_always_viable(self):
        self.assertTrue(is_price_viable(500_000, 50_000))
        self.assertTrue(is_price_viable(9_999_999, 999_999))

    def test_custom_policy(self):
        policy = PriceViabilityPolicy(
            max_markup_pct=10,
            baseline_price_floor=100,
        )
        self.assertTrue(is_price_viable(110, 100, policy=policy))
        self.assertFalse(is_price_viable(111, 100, policy=policy))
        # Below custom floor always counts.
        self.assertTrue(is_price_viable(1_000, 99, policy=policy))

    def test_individual_overrides_win_over_policy(self):
        policy = PriceViabilityPolicy(
            max_markup_pct=10,
            baseline_price_floor=1_000_000,
        )
        self.assertTrue(
            is_price_viable(
                130,
                100,
                policy=policy,
                max_markup_pct=30,
                baseline_price_floor=50,
            )
        )
        self.assertFalse(
            is_price_viable(
                131,
                100,
                policy=policy,
                max_markup_pct=30,
                baseline_price_floor=50,
            )
        )

    def test_sell_order_alias(self):
        self.assertTrue(
            order_quantity_counts_as_reasonable(2_400_000, 2_000_000)
        )
        self.assertFalse(
            order_quantity_counts_as_reasonable(2_400_001, 2_000_000)
        )
