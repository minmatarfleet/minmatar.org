"""Tests for planner stock paste helpers."""

from django.test import TestCase
from eveuniverse.models import EveCategory, EveGroup, EveType

from industry.helpers.plan_stock import (
    apply_stock_to_compressed_ore_plan,
    apply_stock_to_leaf_materials,
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
