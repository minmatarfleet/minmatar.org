"""The LP offers API serves the tax and freight inside each net conversion."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest import TestCase

from industry.endpoints.loyalty.serialization import (
    offer_economics_row_response,
)
from industry.helpers.plan_costing import (
    lp_offer_side_costs,
    plan_lp_offer_conversion,
)
from industry.models import IndustryLpStoreOfferEconomics


def _conversion(price, *, required=500_000, quantity=3):
    return plan_lp_offer_conversion(
        lp_cost=2_000,
        isk_cost=100_000,
        quantity=quantity,
        market_price_isk=price,
        required_items_isk=required,
        build_plan=None,
    )


def _row(**overrides) -> IndustryLpStoreOfferEconomics:
    sell = _conversion(1_234_567)
    buy = _conversion(1_000_001)
    fields = {
        "esi_offer_id": 1,
        "corporation_id": 1000182,
        "type_id": 587,
        "type_name": "Rifter",
        "lp_cost": 2_000,
        "isk_cost": 100_000,
        "quantity": 3,
        "other_cost": 500_000,
        "input_cost_isk": sell.input_isk,
        "input_freight_isk": sell.input_freight.isk,
        "jita_sell": 1_234_567,
        "jita_buy": 1_000_001,
        "jita_avg_7d": None,
        "conversion_isk_per_lp_sell": sell.net_isk_per_lp,
        "conversion_isk_per_lp_buy": buy.net_isk_per_lp,
        "offer_updated_at": datetime(2026, 10, 1, tzinfo=timezone.utc),
    }
    fields.update(overrides)
    return IndustryLpStoreOfferEconomics(**fields)


class LpOfferSideCostsTestCase(TestCase):
    def test_matches_the_conversion_the_rebuild_stores(self):
        for price in (1, 999, 1_234_567, 9_876_543_210):
            conversion = _conversion(price)
            costs = lp_offer_side_costs(
                lp_cost=2_000,
                quantity=3,
                market_price_isk=price,
                input_freight_isk=conversion.input_freight.isk,
            )
            self.assertEqual(
                costs["sales_tax_isk_per_lp"], conversion.sales_tax_isk_per_lp
            )
            self.assertEqual(
                costs["input_freight_isk_per_lp"],
                conversion.input_freight_isk_per_lp,
            )
            self.assertEqual(
                costs["output_freight_isk_per_lp"],
                conversion.output_freight_isk_per_lp,
            )

    def test_components_sum_to_the_net(self):
        conversion = _conversion(1_234_567)
        costs = lp_offer_side_costs(
            lp_cost=2_000,
            quantity=3,
            market_price_isk=1_234_567,
            input_freight_isk=conversion.input_freight.isk,
        )
        net = (
            conversion.raw_isk_per_lp
            - conversion.input_isk_per_lp
            - costs["sales_tax_isk_per_lp"]
            - costs["input_freight_isk_per_lp"]
            - costs["output_freight_isk_per_lp"]
        )
        self.assertAlmostEqual(net, conversion.net_isk_per_lp, places=9)

    def test_missing_price_or_lp(self):
        costs = lp_offer_side_costs(
            lp_cost=2_000,
            quantity=1,
            market_price_isk=None,
            input_freight_isk=None,
        )
        self.assertEqual(
            costs,
            {
                "sales_tax_isk_per_lp": None,
                "input_freight_isk_per_lp": None,
                "output_freight_isk_per_lp": None,
            },
        )
        zero_lp = lp_offer_side_costs(
            lp_cost=0, quantity=1, market_price_isk=10, input_freight_isk=5
        )
        self.assertIsNone(zero_lp["sales_tax_isk_per_lp"])


class OfferResponseConversionCostsTestCase(TestCase):
    def test_serves_costs_for_each_priced_side(self):
        response = offer_economics_row_response(_row())
        self.assertEqual(set(response.conversion_costs), {"sell", "buy"})
        sell = _conversion(1_234_567)
        served = response.conversion_costs["sell"]
        self.assertEqual(
            served.sales_tax_isk_per_lp, sell.sales_tax_isk_per_lp
        )
        self.assertEqual(
            served.output_freight_isk_per_lp, sell.output_freight_isk_per_lp
        )
        self.assertEqual(
            served.input_freight_isk_per_lp, sell.input_freight_isk_per_lp
        )
        self.assertEqual(
            response.conversion_costs["buy"].sales_tax_isk_per_lp,
            _conversion(1_000_001).sales_tax_isk_per_lp,
        )

    def test_unconvertible_row_still_gets_revenue_costs(self):
        response = offer_economics_row_response(
            _row(
                input_cost_isk=None,
                input_freight_isk=None,
                conversion_isk_per_lp_sell=None,
                conversion_isk_per_lp_buy=None,
            )
        )
        sell = response.conversion_costs["sell"]
        self.assertIsNone(sell.input_freight_isk_per_lp)
        self.assertIsNotNone(sell.sales_tax_isk_per_lp)
        self.assertIsNotNone(sell.output_freight_isk_per_lp)
