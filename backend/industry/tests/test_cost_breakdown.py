"""Tests for industry planner cost breakdown aggregation."""

from unittest.mock import patch

from django.test import TestCase
from eveuniverse.models import EveCategory, EveGroup, EveType

from industry.helpers.build_planner import BuildPlan, JobBucket, JobPlan
from industry.helpers.compressed_ore import CompressedOrePlan
from industry.helpers.cost_breakdown import (
    build_plan_cost_breakdown,
    materials_jita_sell_isk_from_named,
    materials_jita_sell_isk_from_type_qtys,
)
from industry.helpers.facility_profiles import JobClass
from industry.helpers.industry_formulas import JobCostBreakdown


def _job_cost(
    *,
    gross: int,
    facility_tax_isk: int = 0,
    scc_tax_isk: int = 0,
) -> JobCostBreakdown:
    tax = facility_tax_isk + scc_tax_isk
    return JobCostBreakdown(
        eiv=1_000_000.0,
        gross_cost=gross,
        tax=tax,
        total=gross + tax,
        system_cost_index=0.05,
        structure_isk_bonus=0.0,
        facility_tax=0.0075,
        scc_surcharge=0.04,
        facility_tax_isk=facility_tax_isk,
        scc_tax_isk=scc_tax_isk,
    )


def _job(
    *,
    activity_id: int,
    gross: int,
    facility_tax_isk: int = 0,
    scc_tax_isk: int = 0,
) -> JobPlan:
    return JobPlan(
        product_type_id=1,
        product_name="Widget",
        activity_id=activity_id,
        job_class=JobClass.SHIP_MANUFACTURING,
        bucket=JobBucket.END_PRODUCT,
        runs=1,
        facility_name="Test",
        blueprint_me=0.1,
        blueprint_te=0.2,
        me_total=0.1,
        te_multiplier=0.8,
        materials=[],
        duration_seconds=100.0,
        job_cost=_job_cost(
            gross=gross,
            facility_tax_isk=facility_tax_isk,
            scc_tax_isk=scc_tax_isk,
        ),
        eiv=1_000_000.0,
    )


class CostBreakdownMathTestCase(TestCase):
    def setUp(self):
        cat, _ = EveCategory.objects.get_or_create(
            id=4, defaults={"name": "Material", "published": True}
        )
        group, _ = EveGroup.objects.get_or_create(
            id=18,
            defaults={
                "name": "Mineral",
                "published": True,
                "eve_category": cat,
            },
        )
        self.trit = EveType.objects.create(
            id=34, name="Tritanium", published=True, eve_group=group
        )
        self.pyer = EveType.objects.create(
            id=35, name="Pyerite", published=True, eve_group=group
        )

    @patch("industry.helpers.cost_breakdown.jita_sell_prices_by_type_id")
    def test_materials_from_type_qtys(self, get_prices):
        get_prices.return_value = {34: 5, 35: 10}
        total = materials_jita_sell_isk_from_type_qtys([(34, 100), (35, 20)])
        self.assertEqual(total, 700)

    @patch("industry.helpers.cost_breakdown.jita_sell_prices_by_type_id")
    def test_materials_from_named(self, get_prices):
        get_prices.return_value = {34: 5, 35: 10}
        total = materials_jita_sell_isk_from_named(
            {"Tritanium": 100, "Pyerite": 20}
        )
        self.assertEqual(total, 700)

    @patch("industry.helpers.cost_breakdown.jita_sell_prices_by_type_id")
    def test_build_plan_cost_breakdown_leaf_materials(self, get_prices):
        get_prices.return_value = {34: 6}
        plan = BuildPlan(
            product_type_id=9001,
            product_name="Hull",
            quantity=2,
            blueprint_me=0.1,
            blueprint_te=0.2,
            facility_key="amamake",
            system_id=1,
            manufacturing_index=0.05,
            reaction_index=0.04,
            jobs=[
                _job(
                    activity_id=1,
                    gross=1_000_000,
                    facility_tax_isk=50_000,
                    scc_tax_isk=200_000,
                ),
                _job(
                    activity_id=11,
                    gross=500_000,
                    facility_tax_isk=10_000,
                    scc_tax_isk=40_000,
                ),
            ],
            leaf_materials={34: ("Tritanium", 1_000)},
        )
        breakdown = build_plan_cost_breakdown(plan)
        self.assertEqual(breakdown.materials_jita_sell_isk, 6_000)
        self.assertEqual(breakdown.manufacturing_job_costs_isk, 1_000_000)
        self.assertEqual(breakdown.reaction_job_costs_isk, 500_000)
        self.assertEqual(breakdown.total_job_costs_isk, 1_500_000)
        self.assertEqual(breakdown.facility_tax_isk, 60_000)
        self.assertEqual(breakdown.scc_tax_isk, 240_000)
        self.assertEqual(breakdown.reprocessing_tax_isk, 0)
        self.assertEqual(breakdown.taxes_isk, 300_000)
        # 6000 + 1_500_000 + 300_000
        self.assertEqual(breakdown.grand_total_isk, 1_806_000)
        self.assertEqual(breakdown.freight_isk, 0)
        self.assertIsNone(breakdown.freight_route_id)
        self.assertEqual(breakdown.output_quantity, 2)
        self.assertAlmostEqual(breakdown.per_unit_isk, 903_000.0)
        keys = [item.key for item in breakdown.line_items]
        self.assertIn("materials_jita_sell", keys)
        self.assertIn("scc_tax", keys)
        self.assertNotIn("freight", keys)
        self.assertNotIn("reprocessing_tax", keys)

    @patch("industry.helpers.cost_breakdown.jita_sell_prices_by_type_id")
    def test_build_plan_cost_breakdown_compressed_reprocessing(
        self, get_prices
    ):
        get_prices.return_value = {34: 5, 35: 10}
        plan = BuildPlan(
            product_type_id=9001,
            product_name="Hull",
            quantity=1,
            blueprint_me=0.1,
            blueprint_te=0.2,
            facility_key="amamake",
            system_id=1,
            manufacturing_index=0.05,
            reaction_index=0.04,
            jobs=[
                _job(
                    activity_id=1,
                    gross=100_000,
                    facility_tax_isk=1_000,
                    scc_tax_isk=4_000,
                ),
            ],
            leaf_materials={34: ("Tritanium", 1_000)},
        )
        ore = CompressedOrePlan(
            refine_rate=0.8,
            reprocessing_tax=0.025,
            belt_ore_compressed={"Compressed Veldspar": 100},
            mineral_imports={"Pyerite": 50},
            expected_minerals={"Tritanium": 1_000},
        )
        # import lines: Compressed Veldspar 100 + Pyerite 50
        # materials = 100*5 + 50*10 = 1000 (if Compressed Veldspar missing from
        # EveType → 0). Create Compressed Veldspar type for pricing.
        EveType.objects.create(
            id=28432,
            name="Compressed Veldspar",
            published=True,
            eve_group=self.trit.eve_group,
        )
        get_prices.return_value = {34: 5, 35: 10, 28432: 20}

        breakdown = build_plan_cost_breakdown(plan, compressed_ore=ore)
        # imports: Compressed Veldspar 100 * 20 + Pyerite 50 * 10 = 2500
        self.assertEqual(breakdown.materials_jita_sell_isk, 2_500)
        # output value Tritanium 1000 * 5 = 5000 → floor(5000 * 0.025) = 125
        self.assertEqual(breakdown.reprocessing_tax_isk, 125)
        self.assertEqual(breakdown.facility_tax_isk, 1_000)
        self.assertEqual(breakdown.scc_tax_isk, 4_000)
        self.assertEqual(
            breakdown.grand_total_isk,
            2_500 + 100_000 + 1_000 + 4_000 + 125,
        )
        self.assertEqual(breakdown.per_unit_isk, breakdown.grand_total_isk)
        keys = [item.key for item in breakdown.line_items]
        self.assertIn("reprocessing_tax", keys)
        reprocess_line = next(
            item
            for item in breakdown.line_items
            if item.key == "reprocessing_tax"
        )
        self.assertEqual(reprocess_line.amount_isk, 125)
