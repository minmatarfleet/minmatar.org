"""Tests for planner freight volume + route cost estimation."""

import math
from unittest.mock import patch

from django.test import TestCase
from eveuniverse.models import EveCategory, EveGroup, EveType

from eveonline.models import EveLocation
from freight.models import EveFreightRoute
from industry.helpers.build_planner import BuildPlan, JobBucket, JobPlan
from industry.helpers.cost_breakdown import build_plan_cost_breakdown
from industry.helpers.facility_profiles import (
    AMAMAKE_SYSTEM_ID,
    BASGERIN_SYSTEM_ID,
    JobClass,
)
from industry.helpers.freight_costs import (
    estimate_freight_cost,
    estimate_plan_freight,
    find_inbound_freight_route,
    materials_volume_m3_from_type_qtys,
)
from industry.helpers.industry_formulas import JobCostBreakdown
from industry.helpers.type_breakdown import ACTIVITY_MANUFACTURING


def _empty_plan(*, facility_key: str = "amamake", leaf=None) -> BuildPlan:
    return BuildPlan(
        product_type_id=9001,
        product_name="Hull",
        quantity=1,
        blueprint_me=0.1,
        blueprint_te=0.2,
        facility_key=facility_key,
        system_id=1,
        manufacturing_index=0.05,
        reaction_index=0.04,
        jobs=[
            JobPlan(
                product_type_id=1,
                product_name="Widget",
                activity_id=ACTIVITY_MANUFACTURING,
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
                job_cost=JobCostBreakdown(
                    eiv=1.0,
                    gross_cost=0,
                    tax=0,
                    total=0,
                    system_cost_index=0.05,
                    structure_isk_bonus=0.0,
                    facility_tax=0.0,
                    scc_surcharge=0.04,
                    facility_tax_isk=0,
                    scc_tax_isk=0,
                ),
                eiv=1.0,
            )
        ],
        leaf_materials=leaf or {},
    )


class FreightCostsTestCase(TestCase):
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
            id=34,
            name="Tritanium",
            published=True,
            eve_group=group,
            volume=0.01,
            packaged_volume=0.01,
        )
        self.jita = EveLocation.objects.create(
            location_id=60003760,
            location_name="Jita IV - Moon 4 - Caldari Navy Assembly Plant",
            short_name="Jita",
            solar_system_id=30000142,
            solar_system_name="Jita",
            price_baseline=True,
            freight_active=True,
        )
        self.amamake = EveLocation.objects.create(
            location_id=1022167642188,
            location_name="Amamake freeport",
            short_name="Amamake",
            solar_system_id=AMAMAKE_SYSTEM_ID,
            solar_system_name="Amamake",
            freight_active=True,
        )
        self.basgerin = EveLocation.objects.create(
            location_id=9990001,
            location_name="Basgerin freeport",
            short_name="Basgerin",
            solar_system_id=BASGERIN_SYSTEM_ID,
            solar_system_name="Basgerin",
            freight_active=True,
        )
        self.route = EveFreightRoute.objects.create(
            origin_location=self.jita,
            destination_location=self.amamake,
            isk_per_m3=600,
            collateral_modifier=0.015,
            active=True,
        )

    def test_materials_volume_from_type_qtys(self):
        volume = materials_volume_m3_from_type_qtys([(34, 1000)])
        self.assertAlmostEqual(volume, 10.0)

    def test_find_inbound_route_amamake(self):
        route = find_inbound_freight_route("amamake")
        self.assertIsNotNone(route)
        self.assertEqual(route.id, self.route.id)

    def test_find_inbound_route_basgerin_none(self):
        self.assertIsNone(find_inbound_freight_route("basgerin"))

    def test_estimate_freight_cost_with_route(self):
        # 10.1 m³ → billable 11; collateral 1_000_000
        # 600*11 + ceil(0.015 * 1_000_000) = 6600 + 15000 = 21600
        est = estimate_freight_cost(
            facility_key="amamake",
            volume_m3=10.1,
            collateral_isk=1_000_000,
        )
        self.assertTrue(est.has_route)
        self.assertEqual(est.billable_m3, 11)
        self.assertEqual(est.freight_isk, 21_600)
        self.assertEqual(est.route_id, self.route.id)
        self.assertIn("Jita", est.route_label)
        self.assertIn("Amamake", est.route_label)

    def test_estimate_freight_cost_no_route(self):
        est = estimate_freight_cost(
            facility_key="basgerin",
            volume_m3=100.0,
            collateral_isk=5_000_000,
        )
        self.assertFalse(est.has_route)
        self.assertEqual(est.freight_isk, 0)
        self.assertEqual(est.billable_m3, 100)
        self.assertAlmostEqual(est.volume_m3, 100.0)

    def test_estimate_plan_freight_from_types(self):
        est = estimate_plan_freight(
            facility_key="amamake",
            type_qtys=[(34, 1000)],
            collateral_isk=100_000,
        )
        # 10 m³ * 600 + ceil(0.015 * 100000) = 6000 + 1500 = 7500
        self.assertEqual(est.billable_m3, 10)
        self.assertEqual(est.freight_isk, 7_500)

    @patch("industry.helpers.cost_breakdown.jita_sell_prices_by_type_id")
    def test_build_plan_includes_freight_when_route_exists(self, get_prices):
        get_prices.return_value = {34: 5}
        plan = _empty_plan(leaf={34: ("Tritanium", 1000)})
        breakdown = build_plan_cost_breakdown(plan)
        # materials 5000; freight 600*10 + ceil(0.015*5000) = 6000 + 75 = 6075
        self.assertEqual(breakdown.materials_jita_sell_isk, 5_000)
        self.assertEqual(breakdown.freight_billable_m3, 10)
        self.assertEqual(breakdown.freight_isk, 6_075)
        self.assertEqual(breakdown.freight_route_id, self.route.id)
        self.assertEqual(
            breakdown.grand_total_isk,
            5_000 + 6_075,
        )
        keys = [item.key for item in breakdown.line_items]
        self.assertIn("freight", keys)

    @patch("industry.helpers.cost_breakdown.jita_sell_prices_by_type_id")
    def test_build_plan_omits_freight_line_without_route(self, get_prices):
        get_prices.return_value = {34: 5}
        plan = _empty_plan(
            facility_key="basgerin",
            leaf={34: ("Tritanium", 1000)},
        )
        breakdown = build_plan_cost_breakdown(plan)
        self.assertAlmostEqual(breakdown.freight_volume_m3, 10.0)
        self.assertEqual(breakdown.freight_isk, 0)
        self.assertIsNone(breakdown.freight_route_id)
        self.assertEqual(breakdown.grand_total_isk, 5_000)
        keys = [item.key for item in breakdown.line_items]
        self.assertNotIn("freight", keys)

    def test_route_cost_matches_ceil_collateral(self):
        est = estimate_freight_cost(
            facility_key="amamake",
            volume_m3=1,
            collateral_isk=100,
        )
        # 600*1 + ceil(1.5) = 600 + 2
        self.assertEqual(est.freight_isk, 600 + math.ceil(0.015 * 100))
