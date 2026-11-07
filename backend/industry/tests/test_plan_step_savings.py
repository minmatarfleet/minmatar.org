"""Tests for the planner's per-step build-vs-buy saving."""

import math
from unittest.mock import patch

from django.test import TestCase
from eveuniverse.models import EveCategory, EveGroup, EveType

from eveonline.models import EveLocation
from freight.models import EveFreightRoute
from industry.helpers.build_planner import (
    BuildPlan,
    JobBucket,
    JobPlan,
    MaterialLine,
)
from industry.helpers.facility_profiles import AMAMAKE_SYSTEM_ID, JobClass
from industry.helpers.industry_formulas import JobCostBreakdown
from industry.helpers.plan_step_savings import plan_step_savings
from industry.helpers.type_breakdown import (
    ACTIVITY_MANUFACTURING,
    ACTIVITY_REACTION,
)

HULL = 9100
COMPONENT = 9101
REACTION = 9102
MINERAL = 9103
GAS = 9104
FUEL = 9105

PRICES = {
    COMPONENT: 1_000,
    REACTION: 50,
    MINERAL: 2,
    GAS: 10,
    FUEL: 20,
}


def _job_cost(gross: int, facility_tax: int = 0, scc: int = 0):
    return JobCostBreakdown(
        eiv=1.0,
        gross_cost=gross,
        tax=facility_tax + scc,
        total=gross + facility_tax + scc,
        system_cost_index=0.05,
        structure_isk_bonus=0.0,
        facility_tax=0.0,
        scc_surcharge=0.04,
        facility_tax_isk=facility_tax,
        scc_tax_isk=scc,
    )


def _job(type_id, name, bucket, materials, *, gross=0, activity=None):
    return JobPlan(
        product_type_id=type_id,
        product_name=name,
        activity_id=activity or ACTIVITY_MANUFACTURING,
        job_class=JobClass.SHIP_MANUFACTURING,
        bucket=bucket,
        runs=1,
        facility_name="Test",
        blueprint_me=0.0,
        blueprint_te=0.0,
        me_total=0.0,
        te_multiplier=1.0,
        materials=[
            MaterialLine(
                type_id=tid,
                name=str(tid),
                quantity=qty,
                base_quantity_per_run=qty,
            )
            for tid, qty in materials
        ],
        duration_seconds=60.0,
        job_cost=_job_cost(gross, facility_tax=5, scc=3),
        eiv=1.0,
    )


def _plan(jobs) -> BuildPlan:
    return BuildPlan(
        product_type_id=HULL,
        product_name="Hull",
        quantity=1,
        blueprint_me=0.0,
        blueprint_te=0.0,
        facility_key="amamake",
        system_id=AMAMAKE_SYSTEM_ID,
        manufacturing_index=0.05,
        reaction_index=0.04,
        jobs=jobs,
    )


def _full_tree():
    # Hull ← 4 Component ← 30 Reaction ← (100 Gas + 2 Fuel)
    #                    ← 200 Mineral
    return _plan(
        [
            _job(
                HULL,
                "Hull",
                JobBucket.END_PRODUCT,
                [(COMPONENT, 4)],
                gross=500,
            ),
            _job(
                COMPONENT,
                "Component",
                JobBucket.ADVANCED_COMPONENTS,
                [(REACTION, 30), (MINERAL, 200)],
                gross=100,
            ),
            _job(
                REACTION,
                "Reaction",
                JobBucket.SECOND_STAGE_REACTIONS,
                [(GAS, 100), (FUEL, 2)],
                gross=40,
                activity=ACTIVITY_REACTION,
            ),
        ]
    )


@patch(
    "industry.helpers.plan_step_savings.jita_sell_prices_by_type_id",
    lambda ids: {tid: PRICES[tid] for tid in ids if tid in PRICES},
)
class PlanStepSavingsTestCase(TestCase):
    def test_each_step_compares_buy_with_build_from_bought_inputs(self):
        rows = {row.type_id: row for row in plan_step_savings(_full_tree())}

        self.assertEqual(set(rows), {COMPONENT, REACTION})

        component = rows[COMPONENT]
        self.assertEqual(component.quantity, 4)
        self.assertEqual(component.buy_isk, 4 * 1_000)
        # 30 reaction × 50 + 200 mineral × 2 + 100 install + 8 taxes.
        self.assertEqual(component.build_isk, 1_500 + 400 + 108)
        self.assertEqual(component.saving_isk, 4_000 - 2_008)

        reaction = rows[REACTION]
        self.assertEqual(reaction.quantity, 30)
        self.assertEqual(reaction.buy_isk, 30 * 50)
        # 100 gas × 10 + 2 fuel × 20 + 40 install + 8 taxes.
        self.assertEqual(reaction.build_isk, 1_000 + 40 + 48)
        self.assertEqual(reaction.saving_isk, 1_500 - 1_088)

    def test_root_product_is_not_a_step(self):
        plan = _plan(
            [_job(HULL, "Hull", JobBucket.END_PRODUCT, [(MINERAL, 10)])]
        )
        self.assertEqual(plan_step_savings(plan), [])

    def test_consumption_sums_every_parent_job(self):
        plan = _full_tree()
        plan.jobs.append(
            _job(
                9106,
                "Other component",
                JobBucket.ADVANCED_COMPONENTS,
                [(REACTION, 12)],
            )
        )
        rows = {row.type_id: row for row in plan_step_savings(plan)}
        self.assertEqual(rows[REACTION].quantity, 42)
        self.assertEqual(rows[REACTION].buy_isk, 42 * 50)

    def test_unpriced_step_has_no_saving(self):
        unpriced = dict(PRICES)
        del unpriced[COMPONENT]
        with patch(
            "industry.helpers.plan_step_savings.jita_sell_prices_by_type_id",
            lambda ids: {tid: unpriced[tid] for tid in ids if tid in unpriced},
        ):
            rows = {
                row.type_id: row for row in plan_step_savings(_full_tree())
            }
        self.assertIsNone(rows[COMPONENT].buy_isk)
        self.assertIsNone(rows[COMPONENT].saving_isk)
        self.assertGreater(rows[COMPONENT].build_isk, 0)
        self.assertIsNotNone(rows[REACTION].saving_isk)


@patch(
    "industry.helpers.plan_step_savings.jita_sell_prices_by_type_id",
    lambda ids: {tid: PRICES[tid] for tid in ids if tid in PRICES},
)
class PlanStepSavingsFreightTestCase(TestCase):
    def setUp(self):
        cat, _ = EveCategory.objects.get_or_create(
            id=17, defaults={"name": "Commodity", "published": True}
        )
        group, _ = EveGroup.objects.get_or_create(
            id=334,
            defaults={
                "name": "Construction Components",
                "published": True,
                "eve_category": cat,
            },
        )
        volumes = {
            COMPONENT: 10.0,
            REACTION: 1.0,
            MINERAL: 0.01,
            GAS: 0.1,
            FUEL: 5.0,
        }
        for type_id, volume in volumes.items():
            EveType.objects.create(
                id=type_id,
                name=f"Type {type_id}",
                published=True,
                eve_group=group,
                volume=volume,
                packaged_volume=volume,
            )
        jita = EveLocation.objects.create(
            location_id=60003760,
            location_name="Jita IV - Moon 4 - Caldari Navy Assembly Plant",
            short_name="Jita",
            solar_system_id=30000142,
            solar_system_name="Jita",
            price_baseline=True,
            freight_active=True,
        )
        amamake = EveLocation.objects.create(
            location_id=1022167642188,
            location_name="Amamake freeport",
            short_name="Amamake",
            solar_system_id=AMAMAKE_SYSTEM_ID,
            solar_system_name="Amamake",
            freight_active=True,
        )
        EveFreightRoute.objects.create(
            origin_location=jita,
            destination_location=amamake,
            isk_per_m3=100,
            collateral_modifier=0.01,
            active=True,
        )

    def test_buy_and_build_include_inbound_freight(self):
        rows = {row.type_id: row for row in plan_step_savings(_full_tree())}
        component = rows[COMPONENT]
        # Buy 4 × 10 m³ = 40 m³ and 4_000 ISK collateral.
        self.assertEqual(
            component.buy_isk, 4_000 + 40 * 100 + math.ceil(0.01 * 4_000)
        )
        # Inputs: 30 × 1 + 200 × 0.01 = 32 m³, 1_900 ISK collateral.
        inputs_isk = 1_500 + 400
        self.assertEqual(
            component.build_isk,
            inputs_isk + 32 * 100 + math.ceil(0.01 * inputs_isk) + 108,
        )
        self.assertEqual(
            component.saving_isk, component.buy_isk - component.build_isk
        )
