"""Tests for planner stock paste helpers."""

from unittest.mock import patch

from django.test import TestCase
from eveuniverse.models import EveCategory, EveGroup, EveType, EveTypeMaterial

from industry.helpers.plan_stock import (
    apply_stock_to_compressed_ore_plan,
    apply_stock_to_leaf_materials,
    credit_reprocessed_ore_stock,
    parse_stock_paste,
)
from industry.helpers.compressed_ore import CompressedOrePlan


class PlanStockHelperTestCase(TestCase):
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
        self.pye = EveType.objects.create(
            id=35, name="Pyerite", published=True, eve_group=group
        )
        ore_cat, _ = EveCategory.objects.get_or_create(
            id=25, defaults={"name": "Asteroid", "published": True}
        )
        ore_group, _ = EveGroup.objects.get_or_create(
            id=465,
            defaults={
                "name": "Veldspar",
                "published": True,
                "eve_category": ore_cat,
            },
        )
        self.veld = EveType.objects.create(
            id=28432,
            name="Compressed Veldspar",
            published=True,
            eve_group=ore_group,
        )

    def test_parse_stock_paste_resolves_and_lists_unknown(self):
        result = parse_stock_paste(
            "Tritanium\t500\nNot A Real Item\t9\npyerite 100"
        )
        self.assertEqual(result.by_type_id[self.trit.id], 500)
        self.assertEqual(result.by_type_id[self.pye.id], 100)
        self.assertEqual(result.by_name["Tritanium"], 500)
        self.assertEqual(result.by_name["Pyerite"], 100)
        self.assertEqual(result.unresolved_names, ["Not A Real Item"])

    def test_apply_stock_partial_and_overstock(self):
        leaf = {
            self.trit.id: ("Tritanium", 1000),
            self.pye.id: ("Pyerite", 50),
        }
        stock = {self.trit.id: 400, self.pye.id: 200}
        remaining, applied = apply_stock_to_leaf_materials(leaf, stock)

        self.assertEqual(remaining[self.trit.id], ("Tritanium", 600))
        self.assertNotIn(self.pye.id, remaining)

        by_name = {row.name: row for row in applied}
        self.assertEqual(by_name["Tritanium"].used, 400)
        self.assertEqual(by_name["Tritanium"].remaining, 600)
        self.assertEqual(by_name["Pyerite"].used, 50)
        self.assertEqual(by_name["Pyerite"].remaining, 0)
        # Stock maps consumed so a later pass cannot double-count.
        self.assertNotIn(self.trit.id, stock)
        self.assertEqual(stock[self.pye.id], 150)

    def test_apply_stock_to_compressed_ore_plan(self):
        ore_plan = CompressedOrePlan(
            belt_ore_compressed={"Compressed Veldspar": 1000},
            mineral_imports={"Pyerite": 80},
            reprocessing_tax=0.025,
        )
        stock_by_name = {
            "Compressed Veldspar": 250,
            "Pyerite": 30,
        }
        applied = apply_stock_to_compressed_ore_plan(
            ore_plan,
            stock_by_name,
            name_to_type_id={
                "Compressed Veldspar": self.veld.id,
                "Pyerite": self.pye.id,
            },
        )
        self.assertEqual(
            ore_plan.belt_ore_compressed["Compressed Veldspar"], 750
        )
        self.assertEqual(ore_plan.mineral_imports["Pyerite"], 50)
        self.assertEqual(ore_plan.reprocessing_tax, 0.025)
        names = {row.name for row in applied}
        self.assertEqual(names, {"Compressed Veldspar", "Pyerite"})

    def test_compressed_ore_stock_clears_reprocessing_tax_when_empty(self):
        ore_plan = CompressedOrePlan(
            belt_ore_compressed={"Compressed Veldspar": 100},
            reprocessing_tax=0.025,
        )
        apply_stock_to_compressed_ore_plan(
            ore_plan, {"Compressed Veldspar": 100}
        )
        self.assertEqual(ore_plan.belt_ore_compressed, {})
        self.assertEqual(ore_plan.reprocessing_tax, 0.0)

    @patch("industry.helpers.compressed_ore._ensure_type_materials_loaded")
    def test_grade_ore_stock_covers_minerals_at_variant_yield(
        self, unused_esi
    ):
        grade = EveType.objects.create(
            id=62522,
            name="Compressed Veldspar II-Grade",
            published=True,
            eve_group=self.veld.eve_group,
        )
        leaf = {self.trit.id: ("Tritanium", 1000)}
        stock_by_type = {grade.id: 500}
        stock_by_name = {
            "Compressed Veldspar II-Grade": 500,
            "Compressed Veldspar": 100,
        }
        applied = credit_reprocessed_ore_stock(
            leaf,
            stock_by_type,
            stock_by_name,
            name_to_type_id={
                "Compressed Veldspar II-Grade": grade.id,
                "Compressed Veldspar": self.veld.id,
            },
            refine_rate_for=lambda _name: 1.0,
        )
        # 420 Tritanium per 100 II-Grade; three portions cover 1000.
        self.assertNotIn(self.trit.id, leaf)
        self.assertEqual(stock_by_name["Compressed Veldspar II-Grade"], 200)
        self.assertEqual(stock_by_name["Compressed Veldspar"], 100)
        self.assertEqual(stock_by_type[grade.id], 200)
        self.assertEqual(applied[0].name, "Compressed Veldspar II-Grade")
        self.assertEqual(applied[0].used, 300)
        self.assertEqual(applied[0].remaining, 200)

    @patch("industry.helpers.compressed_ore._ensure_type_materials_loaded")
    def test_grade_stock_uses_type_materials(self, unused_esi):
        scordite_ii = EveType.objects.create(
            id=17463,
            name="Scordite II-Grade",
            published=True,
            eve_group=self.veld.eve_group,
        )
        EveTypeMaterial.objects.create(
            eve_type=scordite_ii,
            material_eve_type=self.pye,
            quantity=103,
        )
        leaf = {self.pye.id: ("Pyerite", 104)}
        stock_by_name = {"Compressed Scordite II-Grade": 100}
        credit_reprocessed_ore_stock(
            leaf,
            {},
            stock_by_name,
            refine_rate_for=lambda _name: 1.0,
        )
        # SDE is 103 Pyerite, not round(99 * 1.05) = 104.
        self.assertEqual(leaf[self.pye.id], ("Pyerite", 1))
        self.assertEqual(stock_by_name, {})
