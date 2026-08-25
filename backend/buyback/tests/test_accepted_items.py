"""Tests for buyback accepted-item seeding."""

from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from eveuniverse.models import (
    EveIndustryActivityMaterial,
    EveIndustryActivityProduct,
)

from buyback.helpers.accepted_items import (
    compressed_buyback_ore_base,
    compressed_ore_buy_factor,
    compressed_ore_buy_market_name,
    ore_jita_buy_unit,
    seed_accepted_items,
)
from buyback.models import BuybackAcceptedItem
from buyback.tests.helpers import ensure_type
from eveonline.models import EveCharacter
from industry.models import IndustryOrder, IndustryOrderItem, IndustryProduct


def _ensure_type(**kwargs):
    return ensure_type(**kwargs)


class AcceptedItemsSeedTestCase(TestCase):
    def test_compressed_buyback_ore_base_matches_variants(self):
        self.assertEqual(
            compressed_buyback_ore_base("Compressed Veldspar"), "Veldspar"
        )
        self.assertEqual(
            compressed_buyback_ore_base("Compressed Veldspar II-Grade"),
            "Veldspar",
        )
        self.assertEqual(
            compressed_buyback_ore_base("Compressed Brimful Zeolites"),
            "Zeolites",
        )
        self.assertEqual(
            compressed_buyback_ore_base("Compressed Hedbergite III-Grade"),
            "Hedbergite",
        )
        self.assertEqual(
            compressed_buyback_ore_base("Compressed Ytirium"), "Ytirium"
        )
        self.assertEqual(
            compressed_buyback_ore_base("Compressed Crokite IV-Grade"),
            "Crokite",
        )
        self.assertEqual(
            compressed_buyback_ore_base("Compressed Mordunium"), "Mordunium"
        )
        self.assertEqual(
            compressed_buyback_ore_base("Compressed Jaspet"), "Jaspet"
        )
        self.assertEqual(
            compressed_buyback_ore_base("Compressed Hemorphite II-Grade"),
            "Hemorphite",
        )
        self.assertEqual(
            compressed_buyback_ore_base("Compressed Gneiss"), "Gneiss"
        )
        self.assertIsNone(compressed_buyback_ore_base("Veldspar"))
        self.assertIsNone(compressed_buyback_ore_base("Compressed Blue Ice"))
        self.assertIsNone(compressed_buyback_ore_base("Compressed Arkonor"))

    def test_compressed_ore_buy_factor_and_market_name(self):
        self.assertEqual(
            compressed_ore_buy_market_name("Compressed Veldspar II-Grade"),
            "Compressed Veldspar",
        )
        self.assertEqual(compressed_ore_buy_factor("Compressed Veldspar"), 1.0)
        self.assertEqual(
            compressed_ore_buy_factor("Compressed Veldspar II-Grade"), 1.05
        )
        self.assertEqual(
            compressed_ore_buy_factor("Compressed Hedbergite III-Grade"), 1.10
        )
        self.assertEqual(
            compressed_ore_buy_factor("Compressed Crokite IV-Grade"), 1.15
        )
        self.assertEqual(
            compressed_ore_buy_factor("Compressed Brimful Zeolites"), 1.15
        )
        self.assertEqual(
            compressed_ore_buy_factor("Compressed Glistening Coesite"), 2.0
        )
        unit = ore_jita_buy_unit(
            "Compressed Veldspar II-Grade",
            {"Compressed Veldspar": Decimal("10")},
        )
        self.assertEqual(unit, Decimal("10.50"))
        self.assertIsNone(ore_jita_buy_unit("Compressed Veldspar", {}))

    @patch("eveonline.signals.update_character_public_data")
    def test_seed_upserts_allowlist(self, unused_mock_public):
        ore = _ensure_type(
            type_id=62516,
            name="Compressed Veldspar",
            group_id=462,
            group_name="Veldspar",
            category_id=25,
            category_name="Asteroid",
        )
        p1 = _ensure_type(
            type_id=3645,
            name="Water",
            group_id=1042,
            group_name="Basic Commodities - Tier 1",
            category_id=43,
            category_name="Planetary Commodities",
        )
        unused_p1 = _ensure_type(
            type_id=3683,
            name="Oxygen",
            group_id=1042,
            group_name="Basic Commodities - Tier 1",
            category_id=43,
            category_name="Planetary Commodities",
        )
        p2 = _ensure_type(
            type_id=9832,
            name="Coolant",
            group_id=1034,
            group_name="Refined Commodities - Tier 2",
            category_id=43,
            category_name="Planetary Commodities",
        )
        unused_p2 = _ensure_type(
            type_id=3689,
            name="Mechanical Parts",
            group_id=1034,
            group_name="Refined Commodities - Tier 2",
            category_id=43,
            category_name="Planetary Commodities",
        )
        p3 = _ensure_type(
            type_id=2319,
            name="Robotics",
            group_id=1040,
            group_name="Specialized Commodities - Tier 3",
            category_id=43,
            category_name="Planetary Commodities",
        )
        unused_p3 = _ensure_type(
            type_id=2345,
            name="Condensates",
            group_id=1040,
            group_name="Specialized Commodities - Tier 3",
            category_id=43,
            category_name="Planetary Commodities",
        )
        product = _ensure_type(
            type_id=999001,
            name="Test Hull",
            group_id=25,
            group_name="Frigate",
            category_id=6,
            category_name="Ship",
        )
        seal = _ensure_type(
            type_id=57478,
            name="Auto-Integrity Preservation Seal",
            group_id=1136,
            group_name="Construction Components",
            category_id=17,
            category_name="Commodity",
        )
        hull_bp = _ensure_type(
            type_id=999002,
            name="Test Hull Blueprint",
            group_id=105,
            group_name="Blueprint",
            category_id=9,
            category_name="Blueprint",
        )
        seal_bp = _ensure_type(
            type_id=57515,
            name="Auto-Integrity Preservation Seal Blueprint",
            group_id=105,
            group_name="Blueprint",
            category_id=9,
            category_name="Blueprint",
        )
        _ensure_type(
            type_id=34,
            name="Tritanium",
            group_id=18,
            group_name="Mineral",
            category_id=4,
            category_name="Material",
        )
        # Hull blueprint → Seal (subproduct) + Robotics; Seal blueprint → Water (P1).
        EveIndustryActivityProduct.objects.create(
            eve_type=hull_bp,
            activity_id=1,
            product_eve_type=product,
            quantity=1,
        )
        EveIndustryActivityMaterial.objects.create(
            eve_type=hull_bp,
            activity_id=1,
            material_eve_type=seal,
            quantity=1,
        )
        EveIndustryActivityMaterial.objects.create(
            eve_type=hull_bp,
            activity_id=1,
            material_eve_type=p3,
            quantity=1,
        )
        EveIndustryActivityProduct.objects.create(
            eve_type=seal_bp,
            activity_id=1,
            product_eve_type=seal,
            quantity=1,
        )
        EveIndustryActivityMaterial.objects.create(
            eve_type=seal_bp,
            activity_id=1,
            material_eve_type=p1,
            quantity=10,
        )
        IndustryProduct.objects.create(
            eve_type=product,
            strategy="imported",
            breakdown={
                "name": "Test Hull",
                "type_id": product.id,
                "quantity": 1,
                "children": [
                    {
                        "name": "Coolant",
                        "type_id": p2.id,
                        "quantity": 2,
                        "children": [],
                    },
                    {
                        "name": "Robotics",
                        "type_id": p3.id,
                        "quantity": 1,
                        "children": [],
                    },
                ],
            },
        )
        character = EveCharacter.objects.create(
            character_id=9001,
            character_name="Seed Tester",
        )
        order = IndustryOrder.objects.create(
            character=character,
            needed_by=timezone.now().date(),
            public_short_code="ABC",
        )
        IndustryOrderItem.objects.create(
            order=order, eve_type=product, quantity=1
        )
        BuybackAcceptedItem.objects.create(
            eve_type=unused_p1,
            category=BuybackAcceptedItem.Category.P1,
            active=True,
        )
        BuybackAcceptedItem.objects.create(
            eve_type=unused_p2,
            category=BuybackAcceptedItem.Category.P2,
            active=True,
        )
        BuybackAcceptedItem.objects.create(
            eve_type=unused_p3,
            category=BuybackAcceptedItem.Category.P3,
            active=True,
        )

        result = seed_accepted_items()
        # Ore + full published P1/P2 catalog (2 P1 + 2 P2) + order BOM P3.
        self.assertGreaterEqual(result["seeded"], 6)
        self.assertEqual(result["pi_seeded"], 5)
        self.assertTrue(
            BuybackAcceptedItem.objects.filter(
                eve_type=ore, active=True, category="ore"
            ).exists()
        )
        self.assertTrue(
            BuybackAcceptedItem.objects.filter(
                eve_type=p1, active=True, category="p1"
            ).exists()
        )
        # Full P1/P2 catalog: unused types stay active (surplus rate).
        self.assertTrue(
            BuybackAcceptedItem.objects.filter(
                eve_type=unused_p1, active=True, category="p1"
            ).exists()
        )
        self.assertTrue(
            BuybackAcceptedItem.objects.filter(
                eve_type=p2, active=True, category="p2"
            ).exists()
        )
        self.assertTrue(
            BuybackAcceptedItem.objects.filter(
                eve_type=unused_p2, active=True, category="p2"
            ).exists()
        )
        self.assertTrue(
            BuybackAcceptedItem.objects.filter(
                eve_type=p3, active=True, category="p3"
            ).exists()
        )
        # P3 outside BOM lookback is deactivated.
        self.assertFalse(
            BuybackAcceptedItem.objects.filter(
                eve_type=unused_p3, active=True
            ).exists()
        )
        self.assertFalse(
            BuybackAcceptedItem.objects.filter(eve_type_id=34).exists()
        )
