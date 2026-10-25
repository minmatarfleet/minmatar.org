"""Order line pricing: presets, margin and the build-cost floor."""

from decimal import Decimal
from unittest.mock import patch

from django.core.cache import cache
from django.test import SimpleTestCase

from industry.helpers.order_pricing import (
    LinePricing,
    line_pricing,
    resolve_unit_price,
)
from industry.helpers.product_unit_cost import ProductUnitCost
from market.helpers.pricing import BaselineBookRow


def _pricing(floor=137_500_000, buy=138_100_000, split=146_550_000):
    return LinePricing(
        type_id=644,
        quantity=10,
        build_cost_per_unit=floor,
        jita_buy=buy,
        jita_split=split,
        jita_sell=155_000_000,
        ship_in_per_unit=22_500_000,
        jita_delivered=177_500_000,
    )


class ResolveUnitPriceTests(SimpleTestCase):
    def test_preset_above_floor_is_used(self):
        price, basis, margin = resolve_unit_price(_pricing(), "jita_split")
        self.assertEqual(price, 146_550_000)
        self.assertEqual(basis, "jita_split")
        self.assertEqual(margin, 6.6)

    def test_preset_below_floor_falls_back_to_floor(self):
        pricing = _pricing(floor=138_300_000)
        price, basis, margin = resolve_unit_price(pricing, "jita_buy")
        self.assertEqual(price, 138_300_000)
        self.assertEqual(basis, "margin")
        self.assertEqual(margin, 0.0)

    def test_missing_preset_falls_back_to_floor(self):
        price, basis, _ = resolve_unit_price(
            _pricing(split=None), "jita_split"
        )
        self.assertEqual(price, 137_500_000)
        self.assertEqual(basis, "margin")

    def test_margin_over_floor(self):
        price, basis, margin = resolve_unit_price(_pricing(), "margin", 30)
        self.assertEqual(price, 178_750_000)
        self.assertEqual(basis, "margin")
        self.assertEqual(margin, 30.0)

    def test_negative_margin_holds_the_floor(self):
        price, _, margin = resolve_unit_price(_pricing(), "margin", -3)
        self.assertEqual(price, 137_500_000)
        self.assertEqual(margin, 0.0)


class LinePricingTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    @patch("industry.helpers.order_pricing._ship_in_per_unit")
    @patch("industry.helpers.order_pricing.plan_product_unit_cost")
    @patch("industry.helpers.order_pricing.baseline_book")
    def test_uses_the_line_quantity_for_the_floor(self, book, plan, ship_in):
        book.return_value = {
            644: BaselineBookRow(
                sell=Decimal("155000000.00"),
                buy=Decimal("138100000.00"),
                split=Decimal("146550000.00"),
            )
        }
        plan.return_value = ProductUnitCost(
            type_id=644,
            name="Typhoon",
            kind="T1",
            cost_per=137_464_323,
            manufacturing_cost_per=137_464_323,
            jita_sell=155_000_000,
            profit_per=0,
            isk_per_lp=None,
            note=None,
        )
        ship_in.return_value = 22_500_000

        pricing = line_pricing(644, 10)

        plan.assert_called_once_with(644, quantity=10)
        self.assertEqual(pricing.build_cost_per_unit, 137_464_323)
        self.assertEqual(pricing.jita_buy, 138_100_000)
        self.assertEqual(pricing.jita_delivered, 177_500_000)

        line_pricing(644, 10)
        plan.assert_called_once()
