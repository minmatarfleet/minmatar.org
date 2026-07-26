"""Tests for industry planner API endpoints."""

from unittest.mock import patch

import jwt
from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client, TestCase
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

from eveonline.models import EveCharacter, EveCharacterSkill
from industry.helpers.facility_profiles import (
    AMAMAKE_SYSTEM_ID,
    AUNER_SYSTEM_ID,
    BASGERIN_SYSTEM_ID,
)
from industry.helpers.reprocessing_skills import (
    SKILL_COHERENT_ORE_PROCESSING,
    SKILL_REPROCESSING,
    SKILL_REPROCESSING_EFFICIENCY,
    SKILL_SIMPLE_ORE_PROCESSING,
    SKILL_UBIQUITOUS_MOON_ORE_PROCESSING,
)
from industry.models import IndustryLoyaltyPoint, IndustryLpStoreOffer

BASE = "/api/industry/planner"


def _token(user: User) -> str:
    return jwt.encode(
        {"user_id": user.pk}, settings.SECRET_KEY, algorithm="HS256"
    )


class PlannerFacilitiesEndpointTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="planner", password="x")
        self.auth = {"HTTP_AUTHORIZATION": f"Bearer {_token(self.user)}"}

    def test_facilities_public_without_auth(self):
        response = self.client.get(f"{BASE}/facilities")
        self.assertEqual(response.status_code, 200)
        keys = {row["key"] for row in response.json()}
        self.assertEqual(keys, {"amamake", "auner", "basgerin"})

    def test_facilities_list_contains_amamake_and_basgerin(self):
        response = self.client.get(f"{BASE}/facilities", **self.auth)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        keys = {row["key"] for row in data}
        self.assertEqual(keys, {"amamake", "auner", "basgerin"})
        amamake = next(r for r in data if r["key"] == "amamake")
        self.assertEqual(amamake["system_id"], AMAMAKE_SYSTEM_ID)
        self.assertEqual(amamake["system_cost_bonus"], -0.5)
        self.assertIn(
            "Reprocessing Monitor II", amamake["reprocessing"]["rig_name"]
        )
        self.assertEqual(amamake["reprocessing"]["rig_type_id"], 46640)
        self.assertEqual(amamake["reprocessing"]["structure_type_id"], 35836)
        self.assertTrue(amamake["reprocessing"]["effects"])
        expected_refine = (53.0 * 1.06 * 1.055 / 100.0) * 1.15 * 1.10 * 1.10
        self.assertAlmostEqual(
            amamake["reprocessing"]["refine_rate"], expected_refine, places=6
        )
        self.assertAlmostEqual(amamake["reprocessing"]["facility_tax"], 0.025)
        kinds = {s["kind"] for s in amamake["structures"]}
        self.assertEqual(kinds, {"sotiyo", "tatara"})
        sotiyo = next(
            s for s in amamake["structures"] if s["kind"] == "sotiyo"
        )
        self.assertEqual(sotiyo["type_id"], 35827)
        self.assertTrue(sotiyo["effects"])
        rig_ids = {r["type_id"] for r in sotiyo["rigs"]}
        self.assertIn(37180, rig_ids)  # XL Ship Manufacturing Efficiency I
        self.assertIn(45548, rig_ids)  # XL Thukker Component Efficiency
        self.assertIn(37183, rig_ids)  # XL Laboratory Optimization I
        tatara = next(
            s for s in amamake["structures"] if s["kind"] == "tatara"
        )
        self.assertEqual(tatara["type_id"], 35836)
        tatara_rig_ids = {r["type_id"] for r in tatara["rigs"]}
        self.assertIn(46497, tatara_rig_ids)  # L Reactor Efficiency II
        self.assertIn(46640, tatara_rig_ids)  # L Reprocessing Monitor II
        basgerin = next(r for r in data if r["key"] == "basgerin")
        self.assertEqual(basgerin["system_id"], BASGERIN_SYSTEM_ID)
        self.assertEqual(basgerin["system_cost_bonus"], 0.0)
        self.assertAlmostEqual(
            basgerin["reprocessing"]["refine_rate"], expected_refine, places=6
        )
        self.assertAlmostEqual(basgerin["reprocessing"]["facility_tax"], 0.025)
        auner = next(r for r in data if r["key"] == "auner")
        self.assertEqual(auner["system_id"], AUNER_SYSTEM_ID)
        self.assertEqual(auner["system_cost_bonus"], 0.0)
        self.assertEqual(auner["facility_tax"], 0.01)
        self.assertAlmostEqual(
            auner["reprocessing"]["refine_rate"], expected_refine, places=6
        )
        self.assertAlmostEqual(auner["reprocessing"]["facility_tax"], 0.03)
        self.assertIn("Guru Forge", auner["structures"][0]["name"])

    @patch("industry.helpers.facility_api.fetch_system_cost_indices")
    def test_facility_detail_includes_live_indexes(self, fetch_indices):
        fetch_indices.return_value = (0.1238, 0.1155)
        response = self.client.get(f"{BASE}/facilities/amamake", **self.auth)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["indices_from_esi"])
        self.assertAlmostEqual(data["cost_indices"]["manufacturing"], 0.1238)
        self.assertAlmostEqual(data["cost_indices"]["reaction"], 0.1155)
        self.assertEqual(len(data["job_classes"]), 3)
        ship = next(
            jc
            for jc in data["job_classes"]
            if jc["job_class"] == "ship_manufacturing"
        )
        self.assertEqual(ship["structure_type_id"], 35827)
        self.assertEqual(ship["rig_type_id"], 37180)
        self.assertTrue(ship["effects"])
        fetch_indices.assert_called_once_with(AMAMAKE_SYSTEM_ID)

    def test_facility_detail_unknown_404(self):
        response = self.client.get(f"{BASE}/facilities/jita", **self.auth)
        self.assertEqual(response.status_code, 404)


class PlannerSystemEndpointTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="sysuser", password="x")
        self.auth = {"HTTP_AUTHORIZATION": f"Bearer {_token(self.user)}"}

    @patch("industry.helpers.facility_api.fetch_system_cost_indices")
    def test_system_amamake_resolves_facility(self, fetch_indices):
        fetch_indices.return_value = (0.1, 0.2)
        response = self.client.get(
            f"{BASE}/systems/{AMAMAKE_SYSTEM_ID}", **self.auth
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["facility_key"], "amamake")
        self.assertIsNotNone(data["facility"])
        self.assertEqual(data["facility"]["key"], "amamake")
        fetch_indices.assert_called_once_with(AMAMAKE_SYSTEM_ID)

    @patch("industry.helpers.facility_api.fetch_system_cost_indices")
    def test_system_unknown_has_null_facility(self, fetch_indices):
        fetch_indices.return_value = (0.05, 0.06)
        response = self.client.get(f"{BASE}/systems/30000142", **self.auth)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsNone(data["facility_key"])
        self.assertIsNone(data["facility"])
        self.assertAlmostEqual(data["cost_indices"]["manufacturing"], 0.05)


class PlannerPlanEndpointTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="planuser", password="x")
        self.auth = {"HTTP_AUTHORIZATION": f"Bearer {_token(self.user)}"}

        cat, _ = EveCategory.objects.get_or_create(
            id=6, defaults={"name": "Ship", "published": True}
        )
        group, _ = EveGroup.objects.get_or_create(
            id=27,
            defaults={
                "name": "Battleship",
                "published": True,
                "eve_category": cat,
            },
        )
        mineral_cat, _ = EveCategory.objects.get_or_create(
            id=4, defaults={"name": "Material", "published": True}
        )
        mineral_group, _ = EveGroup.objects.get_or_create(
            id=18,
            defaults={
                "name": "Mineral",
                "published": True,
                "eve_category": mineral_cat,
            },
        )
        EveIndustryActivity.objects.get_or_create(
            id=1, defaults={"name": "Manufacturing", "description": "m"}
        )
        self.trit = EveType.objects.create(
            id=34, name="Tritanium", published=True, eve_group=mineral_group
        )
        self.hull = EveType.objects.create(
            id=900200, name="Plan Probe Hull", published=True, eve_group=group
        )
        bp = EveType.objects.create(
            id=900201,
            name="Plan Probe Hull Blueprint",
            published=True,
            eve_group=mineral_group,
        )
        EveIndustryActivityProduct.objects.create(
            eve_type=bp,
            activity_id=1,
            product_eve_type=self.hull,
            quantity=1,
        )
        EveIndustryActivityDuration.objects.create(
            eve_type=bp, activity_id=1, time=18000
        )
        EveIndustryActivityMaterial.objects.create(
            eve_type=bp,
            activity_id=1,
            material_eve_type=self.trit,
            quantity=1000,
        )
        EveMarketPrice.objects.create(
            eve_type=self.trit, adjusted_price=5.0, average_price=6.0
        )

    def test_plan_public_without_auth_uses_max_skills(self):
        with patch(
            "industry.helpers.build_planner.resolve_cost_indices"
        ) as resolve_indices:
            resolve_indices.return_value = (0.05, 0.04, AMAMAKE_SYSTEM_ID)
            response = self.client.post(
                f"{BASE}/plans",
                data={
                    "product_type_id": self.hull.id,
                    "quantity": 1,
                    "blueprint_me": 0,
                    "blueprint_te": 0,
                    "facility_key": "amamake",
                    "compressed": True,
                },
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 200, response.content)
        ore = response.json()["compressed_ore"]
        self.assertEqual(ore["refine_rate_source"], "facility_default")
        self.assertIsNone(ore["character_skills"])

    def test_plan_character_id_requires_auth(self):
        response = self.client.post(
            f"{BASE}/plans",
            data={
                "product_type_id": self.hull.id,
                "quantity": 1,
                "character_id": 2122999001,
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

    @patch("industry.helpers.build_planner.resolve_cost_indices")
    def test_post_plan_returns_jobs_and_leaf_prices(self, resolve_indices):
        resolve_indices.return_value = (0.05, 0.04, AMAMAKE_SYSTEM_ID)
        response = self.client.post(
            f"{BASE}/plans",
            data={
                "product_type_id": self.hull.id,
                "quantity": 2,
                "blueprint_me": 0,
                "blueprint_te": 0,
                "facility_key": "amamake",
            },
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(data["product"]["quantity"], 2)
        self.assertEqual(data["facility"], "amamake")
        self.assertTrue(data["indices_from_esi"])
        self.assertGreaterEqual(len(data["jobs"]), 1)
        leaf = next(m for m in data["leaf_materials"] if m["type_id"] == 34)
        self.assertEqual(leaf["average_price"], 6.0)
        self.assertGreater(leaf["estimated_buy_isk"], 0)
        self.assertGreater(data["estimated_materials_buy_isk"], 0)
        breakdown = data["cost_breakdown"]
        self.assertIsNotNone(breakdown)
        self.assertIn("materials_jita_sell_isk", breakdown)
        self.assertIn("grand_total_isk", breakdown)
        self.assertIn("per_unit_isk", breakdown)
        self.assertEqual(breakdown["output_quantity"], 2)
        self.assertAlmostEqual(
            breakdown["per_unit_isk"],
            breakdown["grand_total_isk"] / 2,
        )
        self.assertGreaterEqual(
            breakdown["grand_total_isk"], breakdown["total_job_costs_isk"]
        )
        line_keys = {row["key"] for row in breakdown["line_items"]}
        self.assertIn("materials_jita_sell", line_keys)
        self.assertIn("facility_tax", line_keys)
        self.assertIn("scc_tax", line_keys)

    @patch("industry.helpers.build_planner.resolve_cost_indices")
    def test_post_plan_omitted_me_te_defaults_to_10_20(self, resolve_indices):
        resolve_indices.return_value = (0.05, 0.04, AMAMAKE_SYSTEM_ID)
        response = self.client.post(
            f"{BASE}/plans",
            data={
                "product_type_id": self.hull.id,
                "quantity": 1,
                "facility_key": "amamake",
            },
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertAlmostEqual(data["blueprint_me"], 0.10)
        self.assertAlmostEqual(data["blueprint_te"], 0.20)

    @patch("industry.helpers.build_planner.resolve_cost_indices")
    def test_post_plan_navy_hull_omitted_me_te_defaults_to_0(
        self, resolve_indices
    ):
        resolve_indices.return_value = (0.05, 0.04, AMAMAKE_SYSTEM_ID)
        navy = EveType.objects.create(
            id=900210,
            name="Plan Probe Navy Issue",
            published=True,
            eve_group=self.hull.eve_group,
        )
        bp = EveType.objects.create(
            id=900211,
            name="Plan Probe Navy Issue Blueprint",
            published=True,
            eve_group=self.trit.eve_group,
        )
        EveIndustryActivityProduct.objects.create(
            eve_type=bp,
            activity_id=1,
            product_eve_type=navy,
            quantity=1,
        )
        EveIndustryActivityDuration.objects.create(
            eve_type=bp, activity_id=1, time=18000
        )
        EveIndustryActivityMaterial.objects.create(
            eve_type=bp,
            activity_id=1,
            material_eve_type=self.trit,
            quantity=1000,
        )
        response = self.client.post(
            f"{BASE}/plans",
            data={
                "product_type_id": navy.id,
                "quantity": 1,
                "facility_key": "amamake",
            },
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertAlmostEqual(data["blueprint_me"], 0.0)
        self.assertAlmostEqual(data["blueprint_te"], 0.0)

    @patch("industry.helpers.build_planner.resolve_cost_indices")
    @patch("industry.helpers.loyalty_store.sync_loyalty_store_offers")
    def test_post_plan_navy_isk_per_lp_adds_bpc_cost(
        self, sync_offers, resolve_indices
    ):
        """Seeded pure LP+ISK offer; plan must not call ESI sync when cached."""
        resolve_indices.return_value = (0.05, 0.04, AMAMAKE_SYSTEM_ID)
        navy = EveType.objects.create(
            id=900230,
            name="Plan Stabber Fleet Issue",
            published=True,
            eve_group=self.hull.eve_group,
        )
        bp = EveType.objects.create(
            id=900231,
            name="Plan Stabber Fleet Issue Blueprint",
            published=True,
            eve_group=self.trit.eve_group,
        )
        EveIndustryActivityProduct.objects.create(
            eve_type=bp,
            activity_id=1,
            product_eve_type=navy,
            quantity=1,
        )
        EveIndustryActivityDuration.objects.create(
            eve_type=bp, activity_id=1, time=18000
        )
        EveIndustryActivityMaterial.objects.create(
            eve_type=bp,
            activity_id=1,
            material_eve_type=self.trit,
            quantity=1000,
        )
        IndustryLpStoreOffer.objects.create(
            offer_id=16343,
            corporation_id=1000182,
            type_id=bp.id,
            lp_cost=100_000,
            isk_cost=20_000_000,
            quantity=1,
        )
        response = self.client.post(
            f"{BASE}/plans",
            data={
                "product_type_id": navy.id,
                "quantity": 2,
                "facility_key": "amamake",
                "isk_per_lp": 800,
            },
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(response.status_code, 200, response.content)
        sync_offers.assert_not_called()
        data = response.json()
        self.assertIsNotNone(data["navy_bpc"])
        self.assertEqual(data["navy_bpc"]["packs"], 2)
        self.assertEqual(data["navy_bpc"]["total_isk"], 200_000_000)
        self.assertEqual(data["cost_breakdown"]["navy_bpc_isk"], 200_000_000)
        line_keys = {
            row["key"] for row in data["cost_breakdown"]["line_items"]
        }
        self.assertIn("navy_bpc_lp", line_keys)

    @patch("industry.helpers.build_planner.resolve_cost_indices")
    def test_post_plan_navy_without_isk_per_lp_uses_loyalty_point_default(
        self, resolve_indices
    ):
        resolve_indices.return_value = (0.05, 0.04, AMAMAKE_SYSTEM_ID)
        navy = EveType.objects.create(
            id=900240,
            name="Plan Scythe Fleet Issue",
            published=True,
            eve_group=self.hull.eve_group,
        )
        bp = EveType.objects.create(
            id=900241,
            name="Plan Scythe Fleet Issue Blueprint",
            published=True,
            eve_group=self.trit.eve_group,
        )
        EveIndustryActivityProduct.objects.create(
            eve_type=bp,
            activity_id=1,
            product_eve_type=navy,
            quantity=1,
        )
        EveIndustryActivityDuration.objects.create(
            eve_type=bp, activity_id=1, time=18000
        )
        EveIndustryActivityMaterial.objects.create(
            eve_type=bp,
            activity_id=1,
            material_eve_type=self.trit,
            quantity=1000,
        )
        IndustryLpStoreOffer.objects.create(
            offer_id=16344,
            corporation_id=1000182,
            type_id=bp.id,
            lp_cost=100_000,
            isk_cost=20_000_000,
            quantity=1,
        )
        IndustryLoyaltyPoint.objects.update_or_create(
            corporation_id=1000182,
            defaults={
                "name": "Tribal Liberation Force",
                "default_isk_per_lp": 800,
                "is_active": True,
            },
        )
        response = self.client.post(
            f"{BASE}/plans",
            data={
                "product_type_id": navy.id,
                "quantity": 1,
                "facility_key": "amamake",
            },
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertIsNotNone(data.get("navy_bpc"))
        self.assertEqual(data["navy_bpc"]["isk_per_lp"], 800.0)
        self.assertEqual(data["navy_bpc"]["total_isk"], 100_000_000)

    @patch("industry.helpers.build_planner.resolve_cost_indices")
    def test_post_plan_explicit_me_te_overrides_navy_default(
        self, resolve_indices
    ):
        resolve_indices.return_value = (0.05, 0.04, AMAMAKE_SYSTEM_ID)
        navy = EveType.objects.create(
            id=900220,
            name="Plan Probe Fleet Issue",
            published=True,
            eve_group=self.hull.eve_group,
        )
        bp = EveType.objects.create(
            id=900221,
            name="Plan Probe Fleet Issue Blueprint",
            published=True,
            eve_group=self.trit.eve_group,
        )
        EveIndustryActivityProduct.objects.create(
            eve_type=bp,
            activity_id=1,
            product_eve_type=navy,
            quantity=1,
        )
        EveIndustryActivityDuration.objects.create(
            eve_type=bp, activity_id=1, time=18000
        )
        EveIndustryActivityMaterial.objects.create(
            eve_type=bp,
            activity_id=1,
            material_eve_type=self.trit,
            quantity=1000,
        )
        response = self.client.post(
            f"{BASE}/plans",
            data={
                "product_type_id": navy.id,
                "quantity": 1,
                "blueprint_me": 5,
                "blueprint_te": 10,
                "facility_key": "amamake",
            },
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertAlmostEqual(data["blueprint_me"], 0.05)
        self.assertAlmostEqual(data["blueprint_te"], 0.10)

    def test_post_plan_unknown_product_400(self):
        response = self.client.post(
            f"{BASE}/plans",
            data={"product_type_id": 999999001, "quantity": 1},
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(response.status_code, 400)

    def test_post_plan_unknown_facility_400(self):
        response = self.client.post(
            f"{BASE}/plans",
            data={
                "product_type_id": self.hull.id,
                "quantity": 1,
                "facility_key": "jita",
            },
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(response.status_code, 400)

    @patch("industry.helpers.build_planner.resolve_cost_indices")
    def test_post_plan_compressed_with_character_skills(self, resolve_indices):
        resolve_indices.return_value = (0.05, 0.04, AMAMAKE_SYSTEM_ID)
        char = EveCharacter.objects.create(
            character_id=2122999001,
            character_name="Plan Char",
        )
        for sid, level, name in (
            (SKILL_REPROCESSING, 5, "Reprocessing"),
            (SKILL_REPROCESSING_EFFICIENCY, 5, "Reprocessing Efficiency"),
            (SKILL_SIMPLE_ORE_PROCESSING, 4, "Simple Ore Processing"),
            (SKILL_COHERENT_ORE_PROCESSING, 5, "Coherent Ore Processing"),
            (
                SKILL_UBIQUITOUS_MOON_ORE_PROCESSING,
                5,
                "Ubiquitous Moon Ore Processing",
            ),
        ):
            EveCharacterSkill.objects.create(
                character=char,
                skill_id=sid,
                skill_name=name,
                skill_points=level * 1000,
                skill_level=level,
            )

        response = self.client.post(
            f"{BASE}/plans",
            data={
                "product_type_id": self.hull.id,
                "quantity": 1,
                "blueprint_me": 0,
                "blueprint_te": 0,
                "facility_key": "amamake",
                "compressed": True,
                "character_id": char.character_id,
            },
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertIn("materials_tsv", data)
        # EVE Multibuy: "Name Quantity" (no header row)
        self.assertNotIn("name\tquantity", data["materials_tsv"])
        self.assertRegex(data["materials_tsv"], r".+ \d+")
        ore = data["compressed_ore"]
        self.assertIsNotNone(ore)
        self.assertEqual(ore["refine_rate_source"], "character")
        self.assertEqual(ore["character_skills"]["ore_processing_level"], 4)
        self.assertEqual(
            ore["character_skills"]["simple_ore_processing_level"], 4
        )
        self.assertEqual(
            ore["character_skills"]["ubiquitous_moon_ore_processing_level"], 5
        )
        yields = {row["ore_name"]: row for row in ore["ore_yields"]}
        self.assertEqual(yields["Veldspar"]["skill_level"], 4)
        self.assertEqual(yields["Plagioclase"]["skill_level"], 4)
        self.assertEqual(yields["Zeolites"]["skill_level"], 5)
        self.assertEqual(
            yields["Veldspar"]["skill_name"], "Simple Ore Processing"
        )
        self.assertEqual(
            yields["Zeolites"]["skill_name"], "Ubiquitous Moon Ore Processing"
        )
        self.assertEqual(
            ore["compression_covered"],
            [
                "Heavy Water",
                "Liquid Ozone",
                "Mexallon",
                "Pyerite",
                "Strontium Clathrates",
                "Tritanium",
            ],
        )
        self.assertNotIn("name\tquantity", ore["materials_tsv"])
        self.assertRegex(ore["materials_tsv"], r".+ \d+")

    @patch("industry.helpers.build_planner.resolve_cost_indices")
    def test_post_plan_refine_override(self, resolve_indices):
        resolve_indices.return_value = (0.05, 0.04, AMAMAKE_SYSTEM_ID)
        response = self.client.post(
            f"{BASE}/plans",
            data={
                "product_type_id": self.hull.id,
                "quantity": 1,
                "blueprint_me": 0,
                "blueprint_te": 0,
                "facility_key": "amamake",
                "compressed": True,
                "refine_rate": 0.80,
            },
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(response.status_code, 200, response.content)
        ore = response.json()["compressed_ore"]
        self.assertEqual(ore["refine_rate_source"], "override")
        self.assertAlmostEqual(ore["refine_rate"], 0.80)
        self.assertEqual(
            ore["compression_covered"],
            [
                "Heavy Water",
                "Liquid Ozone",
                "Mexallon",
                "Pyerite",
                "Strontium Clathrates",
                "Tritanium",
            ],
        )

    @patch("industry.helpers.build_planner.resolve_cost_indices")
    def test_post_plan_exclude_type_ids(self, resolve_indices):
        resolve_indices.return_value = (0.05, 0.04, AMAMAKE_SYSTEM_ID)
        # Build a mini tree: hull needs an intermediate with its own recipe.
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
        adv = EveType.objects.create(
            id=900210, name="Plan Adv", published=True, eve_group=group
        )
        bp_adv = EveType.objects.create(
            id=900211,
            name="Plan Adv Blueprint",
            published=True,
            eve_group=group,
        )
        EveIndustryActivityProduct.objects.create(
            eve_type=bp_adv,
            activity_id=1,
            product_eve_type=adv,
            quantity=1,
        )
        EveIndustryActivityDuration.objects.create(
            eve_type=bp_adv, activity_id=1, time=1000
        )
        EveIndustryActivityMaterial.objects.create(
            eve_type=bp_adv,
            activity_id=1,
            material_eve_type=self.trit,
            quantity=50,
        )
        # Hull recipe already uses trit; add adv requirement via new material line
        EveIndustryActivityMaterial.objects.create(
            eve_type=EveType.objects.get(id=900201),
            activity_id=1,
            material_eve_type=adv,
            quantity=1,
        )

        full = self.client.post(
            f"{BASE}/plans",
            data={
                "product_type_id": self.hull.id,
                "quantity": 1,
                "blueprint_me": 0,
                "blueprint_te": 0,
                "facility_key": "amamake",
            },
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(full.status_code, 200, full.content)
        full_jobs = {j["product_type_id"] for j in full.json()["jobs"]}
        self.assertIn(adv.id, full_jobs)

        trimmed = self.client.post(
            f"{BASE}/plans",
            data={
                "product_type_id": self.hull.id,
                "quantity": 1,
                "blueprint_me": 0,
                "blueprint_te": 0,
                "facility_key": "amamake",
                "exclude_type_ids": [adv.id],
            },
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(trimmed.status_code, 200, trimmed.content)
        data = trimmed.json()
        trimmed_jobs = {j["product_type_id"] for j in data["jobs"]}
        self.assertNotIn(adv.id, trimmed_jobs)
        leaf_ids = {m["type_id"] for m in data["leaf_materials"]}
        self.assertIn(adv.id, leaf_ids)


class PlannerCorsTestCase(TestCase):
    def setUp(self):
        self.client = Client()

    def test_options_preflight_allowed_origin(self):
        response = self.client.options(
            f"{BASE}/plans",
            HTTP_ORIGIN="http://localhost:4321",
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS="authorization,content-type",
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(
            response["Access-Control-Allow-Origin"], "http://localhost:4321"
        )
        self.assertIn("POST", response["Access-Control-Allow-Methods"])
        self.assertIn(
            "Authorization", response["Access-Control-Allow-Headers"]
        )

    def test_options_preflight_unknown_origin_not_short_circuited(self):
        response = self.client.options(
            f"{BASE}/plans",
            HTTP_ORIGIN="https://evil.example",
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
        )
        # Unknown origins fall through to Ninja routing → 405 Method Not Allowed.
        self.assertEqual(response.status_code, 405)
        self.assertNotIn("Access-Control-Allow-Origin", response)
