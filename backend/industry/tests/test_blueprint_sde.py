"""Tests for industry.helpers.blueprint_sde."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.test import TestCase
from eveuniverse.models import (
    EveCategory,
    EveGroup,
    EveIndustryActivityMaterial,
    EveIndustryActivityProduct,
    EveType,
)

from industry.helpers.blueprint_sde import load_missing_blueprints
from industry.helpers.type_breakdown import get_blueprint_or_reaction_type_id
from industry.models import IndustryProduct, Strategy

TFI_TYPE_ID = 95632
TFI_BP_TYPE_ID = 95637
TRITANIUM = 34
SKILL = 3380

TFI_BLUEPRINT = {
    "_key": TFI_BP_TYPE_ID,
    "activities": {
        "copying": {"time": 12000},
        "manufacturing": {
            "materials": [{"quantity": 3640000, "typeID": TRITANIUM}],
            "products": [{"quantity": 1, "typeID": TFI_TYPE_ID}],
            "skills": [{"level": 1, "typeID": SKILL}],
            "time": 15000,
        },
    },
    "maxProductionLimit": 10,
}
OTHER_BLUEPRINT = {
    "_key": 999002,
    "activities": {
        "manufacturing": {
            "products": [{"quantity": 1, "typeID": 999001}],
            "time": 10,
        }
    },
}


class BlueprintSdeTests(TestCase):
    def setUp(self):
        ship = EveCategory.objects.create(id=6, name="Ship", published=True)
        bc = EveGroup.objects.create(
            id=419,
            name="Combat Battlecruiser",
            eve_category=ship,
            published=True,
        )
        bpc = EveCategory.objects.create(
            id=9, name="Blueprint", published=True
        )
        bpg = EveGroup.objects.create(
            id=105,
            name="Battlecruiser Blueprint",
            eve_category=bpc,
            published=True,
        )
        mat = EveCategory.objects.create(id=4, name="Material", published=True)
        misc = EveGroup.objects.create(
            id=18, name="Mineral", eve_category=mat, published=True
        )
        self.tfi = EveType.objects.create(
            id=TFI_TYPE_ID,
            name="Tornado Fleet Issue",
            eve_group=bc,
            published=True,
        )
        EveType.objects.create(
            id=TFI_BP_TYPE_ID,
            name="Tornado Fleet Issue Blueprint",
            eve_group=bpg,
            published=True,
        )
        EveType.objects.create(
            id=TRITANIUM, name="Tritanium", eve_group=misc, published=True
        )
        EveType.objects.create(
            id=SKILL, name="Industry", eve_group=misc, published=True
        )
        with patch(
            "industry.tasks.ensure_loyalty_store_offers_for_product_task.delay"
        ):
            IndustryProduct.objects.create(
                eve_type=self.tfi, strategy=Strategy.IMPORTED
            )

    def _load(self, rows):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "blueprints.jsonl").write_text(
                "\n".join(json.dumps(r) for r in rows), encoding="utf8"
            )
            return load_missing_blueprints(tmp)

    def test_loads_a_blueprint_the_mirror_lacks(self):
        self.assertEqual(self._load([TFI_BLUEPRINT, OTHER_BLUEPRINT]), 1)
        self.assertEqual(
            get_blueprint_or_reaction_type_id(self.tfi), TFI_BP_TYPE_ID
        )
        material = EveIndustryActivityMaterial.objects.get(
            eve_type_id=TFI_BP_TYPE_ID, activity_id=1
        )
        self.assertEqual(material.quantity, 3640000)
        # Types nobody builds or orders are left alone.
        self.assertFalse(
            EveIndustryActivityProduct.objects.filter(
                eve_type_id=999002
            ).exists()
        )

    def test_skips_products_that_already_have_a_recipe(self):
        self._load([TFI_BLUEPRINT])
        self.assertEqual(self._load([TFI_BLUEPRINT]), 0)
        self.assertEqual(
            EveIndustryActivityProduct.objects.filter(
                product_eve_type_id=TFI_TYPE_ID
            ).count(),
            1,
        )
