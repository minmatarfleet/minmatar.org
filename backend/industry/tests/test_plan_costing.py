"""Unit tests for unified plan_costing freight + LP conversion math."""

from __future__ import annotations

import math
from unittest import TestCase

from industry.helpers.plan_costing import (
    DEFAULT_SALES_TAX_RATE,
    RED_FROG_VALUE_RATE,
    FreightMode,
    FreightOptions,
    ItemPlanCost,
    SalesTaxOptions,
    plan_lp_offer_conversion,
)


class FreightOptionsTestCase(TestCase):
    def test_red_frog_rate_is_45m_per_1_5b(self):
        self.assertAlmostEqual(RED_FROG_VALUE_RATE, 0.03, places=10)
        opts = FreightOptions.red_frog_jita_amo()
        self.assertEqual(opts.mode, FreightMode.value_percent)
        self.assertEqual(opts.route_label, "Jita ↔ Amo")
        self.assertEqual(opts.value_label, "Red Frog Freight")

    def test_presets(self):
        self.assertEqual(FreightOptions.off().mode, FreightMode.off)
        self.assertEqual(
            FreightOptions.alliance_default().mode,
            FreightMode.alliance_route,
        )


class PlanLpOfferConversionTestCase(TestCase):
    def test_simple_offer_net_subtracts_tax_and_output_freight(self):
        result = plan_lp_offer_conversion(
            lp_cost=1_000,
            isk_cost=500_000,
            quantity=1,
            market_price_isk=1_500_000,
            required_items_isk=0,
            build_plan=None,
        )
        revenue = 1_500_000
        tax = math.ceil(DEFAULT_SALES_TAX_RATE * revenue)
        out_f = math.ceil(RED_FROG_VALUE_RATE * revenue)
        expected = (revenue - tax - 500_000 - 0 - out_f) / 1_000
        self.assertAlmostEqual(result.net_isk_per_lp, expected)
        self.assertAlmostEqual(result.raw_isk_per_lp, 1_500.0)
        self.assertAlmostEqual(result.input_isk_per_lp, 500.0)
        self.assertEqual(result.input_freight.isk, 0)
        self.assertEqual(result.output_freight.isk, out_f)
        self.assertEqual(result.sales_tax_isk, tax)

    def test_required_items_drive_input_freight(self):
        result = plan_lp_offer_conversion(
            lp_cost=2_000,
            isk_cost=100_000,
            quantity=1,
            market_price_isk=1_500_000,
            required_items_isk=500_000,
            build_plan=None,
        )
        in_f = math.ceil(RED_FROG_VALUE_RATE * 500_000)
        self.assertEqual(result.input_freight.isk, in_f)
        self.assertEqual(result.input_isk, 600_000)

    def test_build_materials_in_freight_basis_jobs_not(self):
        build = ItemPlanCost(
            type_id=1,
            name="Hull",
            materials_jita_sell_isk=40_000_000,
            total_job_costs_isk=5_000_000,
            taxes_isk=5_000_000,
            manufacturing_isk=50_000_000,
        )
        result = plan_lp_offer_conversion(
            lp_cost=100_000,
            isk_cost=20_000_000,
            quantity=1,
            market_price_isk=250_000_000,
            required_items_isk=0,
            build_plan=build,
        )
        # Input includes materials+jobs+taxes, not freight on jobs alone.
        self.assertEqual(result.input_isk, 20_000_000 + 50_000_000)
        self.assertEqual(
            result.input_freight.isk,
            math.ceil(RED_FROG_VALUE_RATE * 40_000_000),
        )

    def test_freight_and_tax_can_be_disabled(self):
        result = plan_lp_offer_conversion(
            lp_cost=1_000,
            isk_cost=500_000,
            quantity=1,
            market_price_isk=1_500_000,
            required_items_isk=0,
            input_freight=FreightOptions.off(),
            output_freight=FreightOptions.off(),
            sales_tax=SalesTaxOptions.off(),
        )
        self.assertAlmostEqual(result.net_isk_per_lp, 1_000.0)
        self.assertEqual(result.sales_tax_isk, 0)
        self.assertEqual(result.output_freight.isk, 0)
