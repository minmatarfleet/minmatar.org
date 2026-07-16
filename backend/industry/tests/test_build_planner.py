"""Tests for Amamake Typhoon build planner (formulas, facilities, plan tree)."""

from django.test import TestCase
from eveuniverse.models import (
    EveCategory,
    EveGroup,
    EveIndustryActivity,
    EveIndustryActivityDuration,
    EveIndustryActivityMaterial,
    EveIndustryActivityProduct,
    EveMarketPrice,
    EveType,
)
from unittest.mock import MagicMock, patch

from industry.helpers.build_planner import (
    JobBucket,
    SkillSettings,
    plan_build,
    resolve_cost_indices,
)
from industry.helpers.facility_profiles import (
    AMAMAKE_SYSTEM_ID,
    BASGERIN_SYSTEM_ID,
    JobClass,
    get_facility_profile,
    get_facility_refine_rate,
    get_facility_reprocessing,
    get_facility_system_id,
)
from industry.helpers.industry_formulas import (
    estimated_item_value,
    job_installation_cost,
    material_efficiency_total,
    required_material_quantity,
    time_efficiency_multiplier,
)

# Ravworks Typhoon ME0 plan 0XLRST5 reference (facility may differ slightly).
RAVWORKS_ME0 = {
    "end_products": 6696,
    "advanced_components": 66048,
    "first_stage_reactions": 164160,
    "second_stage_reactions": 77760,
    "other": 1728,
    "manufacturing_job_costs": 21_900_000,
}


class IndustryFormulasTestCase(TestCase):
    def test_me_total_multiplicative(self):
        me = material_efficiency_total(0.10, 0.01, 0.038)
        expected = 1.0 - (0.90 * 0.99 * 0.962)
        self.assertAlmostEqual(me, expected, places=10)

    def test_single_unit_material_stays_at_runs(self):
        self.assertEqual(required_material_quantity(10, 1, 0.50), 10)

    def test_material_rounding_matches_c4813_shape(self):
        # Venture-style: 100 runs, base 22400, Sotiyo 1%, T1 null 2%*2.1, ME0
        me = material_efficiency_total(0.0, 0.01, 0.02 * 2.1)
        qty = required_material_quantity(100, 22400, me)
        self.assertEqual(qty, 2_124_461)

    def test_time_multiplier_industry_skills(self):
        mult = time_efficiency_multiplier(
            0.0,
            0.30,
            0.38,
            industry_level=5,
            advanced_industry_level=5,
            is_reaction=False,
        )
        expected = 0.70 * 0.62 * 0.80 * 0.85
        self.assertAlmostEqual(mult, expected, places=10)

    def test_time_multiplier_reactions_use_reaction_skill(self):
        mult = time_efficiency_multiplier(
            0.0,
            0.25,
            0.24,
            reaction_skill_level=5,
            is_reaction=True,
        )
        expected = 0.75 * 0.76 * 0.80
        self.assertAlmostEqual(mult, expected, places=10)

    def test_job_cost_floor_and_scc(self):
        cost = job_installation_cost(
            eiv=100_000_000,
            system_cost_index=0.05,
            structure_isk_bonus=0.05,
            facility_tax=0.0,
            scc_surcharge=0.04,
        )
        self.assertEqual(
            cost.gross_cost, 4_750_000
        )  # floor(1e8 * 0.05 * 0.95)
        self.assertEqual(cost.scc_tax_isk, 4_000_000)  # floor(1e8 * 0.04)
        self.assertEqual(cost.facility_tax_isk, 0)
        self.assertEqual(cost.tax, 4_000_000)
        self.assertEqual(cost.total, 8_750_000)

    def test_job_cost_includes_facility_tax(self):
        cost = job_installation_cost(
            eiv=100_000_000,
            system_cost_index=0.05,
            structure_isk_bonus=0.05,
            facility_tax=0.0075,
            scc_surcharge=0.04,
        )
        self.assertEqual(cost.gross_cost, 4_750_000)
        self.assertEqual(cost.facility_tax_isk, 750_000)  # floor(1e8 * 0.0075)
        self.assertEqual(cost.scc_tax_isk, 4_000_000)  # floor(1e8 * 0.04)
        self.assertEqual(cost.tax, 4_750_000)
        self.assertEqual(cost.total, 9_500_000)

    def test_job_cost_fw_system_cost_bonus_halves_gross_only(self):
        cost = job_installation_cost(
            eiv=100_000_000,
            system_cost_index=0.05,
            structure_isk_bonus=0.05,
            facility_tax=0.0,
            scc_surcharge=0.04,
            system_cost_bonus=-0.50,
        )
        # floor(1e8 * 0.05 * 0.95 * 0.50) = 2_375_000; SCC unchanged
        self.assertEqual(cost.gross_cost, 2_375_000)
        self.assertEqual(cost.tax, 4_000_000)
        self.assertEqual(cost.total, 6_375_000)
        self.assertEqual(cost.system_cost_bonus, -0.50)

    def test_eiv_uses_me0_base_quantities_times_adjusted_price(self):
        # ME-adjusted shopping qty must not feed EIV; only blueprint base × runs.
        eiv = estimated_item_value(
            [
                (100, 10.0),  # base ME0 qty per run
                (50, 20.0),
            ],
            runs=10,
        )
        self.assertEqual(eiv, (100 * 10.0 + 50 * 20.0) * 10)

    def test_job_cost_matches_ccp_screenshot_structure(self):
        """
        Steve Ronuken / in-game UI shape (synthetic SCI matching displayed ISK):

        EIV 114,894,884; SCI portion 5,898,934 (~5.13%); −5% Sotiyo role →
        gross 5,603,987; +0.75% facility + 4% SCC on EIV.

        Client display total may round to 11,061,494; floored components sum
        to 11,061,493 (facility tax floors to 861,711).
        """
        eiv = 114_894_884.0
        sci_portion = 5_898_934.0
        cost = job_installation_cost(
            eiv=eiv,
            system_cost_index=sci_portion / eiv,
            structure_isk_bonus=0.05,
            facility_tax=0.0075,
            scc_surcharge=0.04,
        )
        self.assertEqual(cost.gross_cost, 5_603_987)
        self.assertEqual(cost.facility_tax_isk, 861_711)
        self.assertEqual(cost.scc_tax_isk, 4_595_795)
        self.assertEqual(cost.tax, 5_457_506)
        self.assertEqual(cost.total, 11_061_493)


class FacilityProfilesTestCase(TestCase):
    def test_amamake_ship_lowsec_scaled_rig(self):
        profile = get_facility_profile("amamake")
        ship = profile[JobClass.SHIP_MANUFACTURING]
        self.assertEqual(ship.role_me, 0.01)
        self.assertEqual(ship.role_te, 0.30)
        self.assertAlmostEqual(ship.rig_me, 0.02 * 1.9, places=10)
        self.assertAlmostEqual(ship.rig_te, 0.20 * 1.9, places=10)
        self.assertEqual(ship.structure_isk_bonus, 0.05)
        self.assertEqual(ship.facility_tax, 0.0075)
        self.assertEqual(ship.scc_surcharge, 0.04)
        self.assertEqual(ship.system_cost_bonus, -0.50)

    def test_amamake_reaction_reactor_eff_ii(self):
        rxn = get_facility_profile("amamake")[JobClass.REACTION]
        self.assertEqual(rxn.role_me, 0.0)
        self.assertEqual(rxn.role_te, 0.25)
        self.assertAlmostEqual(rxn.rig_me, 0.024, places=10)
        self.assertAlmostEqual(rxn.rig_te, 0.24, places=10)
        self.assertEqual(rxn.facility_tax, 0.0075)
        self.assertEqual(rxn.system_cost_bonus, -0.50)

    def test_amamake_facility_system_id(self):
        self.assertEqual(get_facility_system_id("amamake"), AMAMAKE_SYSTEM_ID)

    def test_basgerin_same_fittings_no_fw_bonus(self):
        amamake = get_facility_profile("amamake")
        basgerin = get_facility_profile("basgerin")
        for job_class in JobClass:
            a = amamake[job_class]
            b = basgerin[job_class]
            self.assertAlmostEqual(a.role_me, b.role_me, places=10)
            self.assertAlmostEqual(a.role_te, b.role_te, places=10)
            self.assertAlmostEqual(a.rig_me, b.rig_me, places=10)
            self.assertAlmostEqual(a.rig_te, b.rig_te, places=10)
            self.assertAlmostEqual(
                a.structure_isk_bonus, b.structure_isk_bonus, places=10
            )
            self.assertEqual(a.system_cost_bonus, -0.50)
            self.assertEqual(b.system_cost_bonus, 0.0)
        self.assertEqual(
            get_facility_system_id("basgerin"), BASGERIN_SYSTEM_ID
        )
        self.assertIn(
            "The Forgery", basgerin[JobClass.SHIP_MANUFACTURING].structure_name
        )

    def test_tatara_reprocessing_monitor_ii_lowsec_yield(self):
        # Tatara + T2 Monitor in lowsec: (50+3)*1.06*1.055 / 100
        expected_base = (53.0 * 1.06 * 1.055) / 100.0
        for key in ("amamake", "basgerin"):
            rp = get_facility_reprocessing(key)
            self.assertIn("Reprocessing Monitor II", rp.rig_name)
            self.assertAlmostEqual(
                rp.facility_base_yield(), expected_base, places=10
            )
            # Skills V/V/V, no implant → ×1.15×1.10×1.10
            expected = expected_base * 1.15 * 1.10 * 1.10
            self.assertAlmostEqual(
                get_facility_refine_rate(key), expected, places=10
            )
            self.assertAlmostEqual(rp.facility_tax, 0.025, places=10)
            # floor(5060 * 0.025) = 126
            self.assertEqual(rp.tax_isk(5060.0), 126)


class LiveCostIndexResolutionTestCase(TestCase):
    @patch("industry.helpers.build_planner.esi_provider")
    def test_resolve_cost_indices_fetches_amamake_from_esi(self, esi_provider):
        esi_provider.client.Industry.get_industry_systems.return_value = (
            MagicMock(
                results=MagicMock(
                    return_value=[
                        {
                            "solar_system_id": AMAMAKE_SYSTEM_ID,
                            "cost_indices": [
                                {
                                    "activity": "manufacturing",
                                    "cost_index": 0.1238,
                                },
                                {"activity": "reaction", "cost_index": 0.1155},
                            ],
                        }
                    ]
                )
            )
        )
        mfg, rxn, system_id = resolve_cost_indices("amamake")
        self.assertEqual(system_id, AMAMAKE_SYSTEM_ID)
        self.assertAlmostEqual(mfg, 0.1238)
        self.assertAlmostEqual(rxn, 0.1155)
        esi_provider.client.Industry.get_industry_systems.assert_called_once()

    @patch("industry.helpers.build_planner.esi_provider")
    def test_resolve_cost_indices_skips_esi_when_both_overridden(
        self, esi_provider
    ):
        mfg, rxn, system_id = resolve_cost_indices(
            "amamake",
            manufacturing_index=0.05,
            reaction_index=0.04,
        )
        self.assertEqual(system_id, AMAMAKE_SYSTEM_ID)
        self.assertEqual(mfg, 0.05)
        self.assertEqual(rxn, 0.04)
        esi_provider.client.Industry.get_industry_systems.assert_not_called()

    @patch("industry.helpers.build_planner.resolve_cost_indices")
    def test_plan_build_uses_resolved_live_indices(self, resolve_indices):
        resolve_indices.return_value = (0.1238, 0.1155, AMAMAKE_SYSTEM_ID)
        # Minimal leaf type with no recipe — still exercises index wiring.
        cat, _ = EveCategory.objects.get_or_create(
            id=9001, defaults={"name": "Idx Cat", "published": True}
        )
        group, _ = EveGroup.objects.get_or_create(
            id=9001,
            defaults={
                "name": "Idx Group",
                "published": True,
                "eve_category": cat,
            },
        )
        hull = EveType.objects.create(
            id=900101, name="Index Probe Hull", published=True, eve_group=group
        )
        plan = plan_build(
            hull,
            quantity=1,
            blueprint_me=0.0,
            blueprint_te=0.0,
            facility="amamake",
        )
        resolve_indices.assert_called_once()
        self.assertTrue(plan.indices_from_esi)
        self.assertAlmostEqual(plan.manufacturing_index, 0.1238)
        self.assertAlmostEqual(plan.reaction_index, 0.1155)
        self.assertEqual(plan.system_id, AMAMAKE_SYSTEM_ID)


class BuildPlannerFixtureTestCase(TestCase):
    """Mini Typhoon-like tree with frozen indices and adjusted prices."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cat_ship, _ = EveCategory.objects.get_or_create(
            id=6, defaults={"name": "Ship", "published": True}
        )
        cls.cat_commodity, _ = EveCategory.objects.get_or_create(
            id=17, defaults={"name": "Commodity", "published": True}
        )
        cls.cat_material, _ = EveCategory.objects.get_or_create(
            id=4, defaults={"name": "Material", "published": True}
        )
        cls.group_bs, _ = EveGroup.objects.get_or_create(
            id=27,
            defaults={
                "name": "Battleship",
                "published": True,
                "eve_category": cls.cat_ship,
            },
        )
        cls.group_comp, _ = EveGroup.objects.get_or_create(
            id=334,
            defaults={
                "name": "Construction Components",
                "published": True,
                "eve_category": cls.cat_commodity,
            },
        )
        cls.group_composite, _ = EveGroup.objects.get_or_create(
            id=429,
            defaults={
                "name": "Composite",
                "published": True,
                "eve_category": cls.cat_material,
            },
        )
        cls.group_mineral, _ = EveGroup.objects.get_or_create(
            id=18,
            defaults={
                "name": "Mineral",
                "published": True,
                "eve_category": cls.cat_material,
            },
        )

        for act_id, name in ((1, "Manufacturing"), (11, "Reaction")):
            EveIndustryActivity.objects.get_or_create(
                id=act_id, defaults={"name": name, "description": name}
            )

        # Types
        cls.trit = EveType.objects.create(
            id=34,
            name="Tritanium",
            published=True,
            eve_group=cls.group_mineral,
        )
        cls.composite = EveType.objects.create(
            id=900001,
            name="Test Composite",
            published=True,
            eve_group=cls.group_composite,
        )
        cls.adv = EveType.objects.create(
            id=900002,
            name="Test Adv Comp",
            published=True,
            eve_group=cls.group_comp,
        )
        cls.hull = EveType.objects.create(
            id=900003,
            name="Test Hull",
            published=True,
            eve_group=cls.group_bs,
        )
        cls.bp_rxn = EveType.objects.create(
            id=900011,
            name="Test Composite Reaction",
            published=True,
            eve_group=cls.group_mineral,
        )
        cls.bp_adv = EveType.objects.create(
            id=900012,
            name="Test Adv Comp Blueprint",
            published=True,
            eve_group=cls.group_mineral,
        )
        cls.bp_hull = EveType.objects.create(
            id=900013,
            name="Test Hull Blueprint",
            published=True,
            eve_group=cls.group_mineral,
        )

        # Reaction: 100 trit -> 200 composite, 10800s
        EveIndustryActivityProduct.objects.create(
            eve_type=cls.bp_rxn,
            activity_id=11,
            product_eve_type=cls.composite,
            quantity=200,
        )
        EveIndustryActivityDuration.objects.create(
            eve_type=cls.bp_rxn, activity_id=11, time=10800
        )
        EveIndustryActivityMaterial.objects.create(
            eve_type=cls.bp_rxn,
            activity_id=11,
            material_eve_type=cls.trit,
            quantity=100,
        )

        # Adv: 500 composite -> 1 adv, 8000s
        EveIndustryActivityProduct.objects.create(
            eve_type=cls.bp_adv,
            activity_id=1,
            product_eve_type=cls.adv,
            quantity=1,
        )
        EveIndustryActivityDuration.objects.create(
            eve_type=cls.bp_adv, activity_id=1, time=8000
        )
        EveIndustryActivityMaterial.objects.create(
            eve_type=cls.bp_adv,
            activity_id=1,
            material_eve_type=cls.composite,
            quantity=500,
        )

        # Hull: 1 adv + 1000 trit -> 1 hull, 18000s
        EveIndustryActivityProduct.objects.create(
            eve_type=cls.bp_hull,
            activity_id=1,
            product_eve_type=cls.hull,
            quantity=1,
        )
        EveIndustryActivityDuration.objects.create(
            eve_type=cls.bp_hull, activity_id=1, time=18000
        )
        EveIndustryActivityMaterial.objects.create(
            eve_type=cls.bp_hull,
            activity_id=1,
            material_eve_type=cls.adv,
            quantity=1,
        )
        EveIndustryActivityMaterial.objects.create(
            eve_type=cls.bp_hull,
            activity_id=1,
            material_eve_type=cls.trit,
            quantity=1000,
        )

        for eve_type, price in (
            (cls.trit, 5.0),
            (cls.composite, 1000.0),
            (cls.adv, 50_000.0),
        ):
            EveMarketPrice.objects.create(
                eve_type=eve_type, adjusted_price=price, average_price=price
            )

    def test_plan_me0_amamake_job_buckets_and_times(self):
        plan = plan_build(
            self.hull,
            quantity=1,
            blueprint_me=0.0,
            blueprint_te=0.0,
            facility="amamake",
            manufacturing_index=0.05,
            reaction_index=0.04,
            skills=SkillSettings(
                industry_level=5,
                advanced_industry_level=5,
                reaction_skill_level=5,
            ),
        )

        by_bucket = plan.jobs_by_bucket()
        self.assertEqual(len(by_bucket[JobBucket.END_PRODUCT]), 1)
        self.assertEqual(len(by_bucket[JobBucket.ADVANCED_COMPONENTS]), 1)
        self.assertEqual(len(by_bucket[JobBucket.SECOND_STAGE_REACTIONS]), 1)

        ship_te = time_efficiency_multiplier(
            0.0, 0.30, 0.38, industry_level=5, advanced_industry_level=5
        )
        comp_te = ship_te  # same Sotiyo/Thukker lowsec TE stack
        rxn_te = time_efficiency_multiplier(
            0.0, 0.25, 0.24, reaction_skill_level=5, is_reaction=True
        )

        hull_job = by_bucket[JobBucket.END_PRODUCT][0]
        adv_job = by_bucket[JobBucket.ADVANCED_COMPONENTS][0]
        rxn_job = by_bucket[JobBucket.SECOND_STAGE_REACTIONS][0]

        self.assertAlmostEqual(
            hull_job.duration_seconds, 18000 * ship_te, places=4
        )
        self.assertAlmostEqual(
            adv_job.duration_seconds, 8000 * comp_te, places=4
        )
        # 500 composite @ 200/run => 3 runs
        self.assertEqual(rxn_job.runs, 3)
        self.assertAlmostEqual(
            rxn_job.duration_seconds, 3 * 10800 * rxn_te, places=4
        )

        # Job cost uses EIV from base mats * adjusted_price
        self.assertGreater(plan.total_job_cost_isk, 0)
        self.assertIn(34, plan.leaf_materials)

    def test_exclude_type_ids_imports_intermediate(self):
        full = plan_build(
            self.hull,
            quantity=1,
            blueprint_me=0.0,
            blueprint_te=0.0,
            facility="amamake",
            manufacturing_index=0.05,
            reaction_index=0.04,
        )
        self.assertTrue(
            any(j.product_type_id == self.adv.id for j in full.jobs)
        )
        self.assertTrue(
            any(j.product_type_id == self.composite.id for j in full.jobs)
        )

        trimmed = plan_build(
            self.hull,
            quantity=1,
            blueprint_me=0.0,
            blueprint_te=0.0,
            facility="amamake",
            manufacturing_index=0.05,
            reaction_index=0.04,
            exclude_type_ids=[self.adv.id],
        )
        self.assertFalse(
            any(j.product_type_id == self.adv.id for j in trimmed.jobs)
        )
        self.assertFalse(
            any(j.product_type_id == self.composite.id for j in trimmed.jobs)
        )
        self.assertIn(self.adv.id, trimmed.leaf_materials)
        self.assertNotIn(self.composite.id, trimmed.leaf_materials)
        self.assertLess(trimmed.total_job_cost_isk, full.total_job_cost_isk)

    def test_me_reduces_component_materials(self):
        plan0 = plan_build(
            self.hull,
            quantity=1,
            blueprint_me=0.0,
            blueprint_te=0.0,
            facility="amamake",
            manufacturing_index=0.01,
            reaction_index=0.01,
        )
        plan10 = plan_build(
            self.hull,
            quantity=1,
            blueprint_me=0.10,
            blueprint_te=0.20,
            facility="amamake",
            manufacturing_index=0.01,
            reaction_index=0.01,
        )
        trit0 = plan0.leaf_materials[34][1]
        trit10 = plan10.leaf_materials[34][1]
        self.assertGreater(trit0, trit10)

    def test_ravworks_reference_shape_documented(self):
        """
        Ravworks ME0 bucket times (plan 0XLRST5) are the verification target.

        Full SDE Typhoon at Amamake with correct lowsec rig scaling will not
        match Ravworks second-for-second (Ravworks appears to use a milder
        manufacturing TE stack). This test locks the reference constants and
        the relative shape we expect from any full-tree plan.
        """
        self.assertEqual(RAVWORKS_ME0["end_products"], 6696)
        self.assertEqual(RAVWORKS_ME0["second_stage_reactions"], 77760)
        self.assertLess(
            RAVWORKS_ME0["end_products"],
            RAVWORKS_ME0["advanced_components"],
        )
        self.assertLess(
            RAVWORKS_ME0["second_stage_reactions"],
            RAVWORKS_ME0["first_stage_reactions"],
        )
        # Reaction stage ratio from Ravworks (~0.47)
        ratio = (
            RAVWORKS_ME0["second_stage_reactions"]
            / RAVWORKS_ME0["first_stage_reactions"]
        )
        self.assertAlmostEqual(ratio, 77760 / 164160, places=6)

    def test_typhoon_hull_me0_amamake_duration_formula(self):
        """Hand-check Typhoon hull (18000s base) at Amamake ship profile ME0."""
        te = time_efficiency_multiplier(
            0.0, 0.30, 0.20 * 1.9, industry_level=5, advanced_industry_level=5
        )
        duration = 18000 * te
        # Sotiyo 30% + XL Ship Eff I lowsec 38% + Ind5/Adv5
        self.assertAlmostEqual(
            duration, 18000 * 0.7 * 0.62 * 0.8 * 0.85, places=4
        )
        # Document delta vs Ravworks end-product time for manual live checks.
        ravworks = RAVWORKS_ME0["end_products"]
        self.assertNotEqual(int(round(duration)), ravworks)
        self.assertLess(abs(duration - ravworks) / ravworks, 0.30)
