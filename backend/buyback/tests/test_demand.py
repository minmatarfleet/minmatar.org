"""Tests for buyback supply-chain demand rates."""

from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.test import Client, TestCase
from django.utils import timezone
from eveuniverse.models import (
    EveIndustryActivityMaterial,
    EveIndustryActivityProduct,
)

from buyback.helpers.demand import demand_type_ids_from_recent_orders
from buyback.models import BuybackAcceptedItem, EveBuybackSettings
from buyback.tests.helpers import BASE_URL, ensure_type
from eveonline.models import EveCharacter, EveLocation
from industry.models import IndustryOrder, IndustryOrderItem, IndustryProduct
from market.models import EveMarketItemHistory


def _ensure_type(**kwargs):
    return ensure_type(**kwargs)


class DemandBuybackRateTestCase(TestCase):
    @patch("eveonline.signals.update_character_public_data")
    def test_demand_from_order_blueprint_imports(self, unused_mock):
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
        hull = _ensure_type(
            type_id=999010,
            name="Demand Hull",
            group_id=25,
            group_name="Frigate",
            category_id=6,
            category_name="Ship",
        )
        hull_bp = _ensure_type(
            type_id=999011,
            name="Demand Hull Blueprint",
            group_id=105,
            group_name="Blueprint",
            category_id=9,
            category_name="Blueprint",
        )
        EveIndustryActivityProduct.objects.create(
            eve_type=hull_bp,
            activity_id=1,
            product_eve_type=hull,
            quantity=1,
        )
        EveIndustryActivityMaterial.objects.create(
            eve_type=hull_bp,
            activity_id=1,
            material_eve_type=p2,
            quantity=5,
        )
        IndustryProduct.objects.create(eve_type=hull, strategy="imported")
        character = EveCharacter.objects.create(
            character_id=9101,
            character_name="Demand Tester",
        )
        order = IndustryOrder.objects.create(
            character=character,
            needed_by=timezone.now().date(),
            public_short_code="DEM",
        )
        IndustryOrderItem.objects.create(
            order=order, eve_type=hull, quantity=1
        )

        demand_ids = demand_type_ids_from_recent_orders()
        self.assertIn(p2.id, demand_ids)
        self.assertNotIn(unused_p2.id, demand_ids)

    @patch("eveonline.signals.update_character_public_data")
    def test_appraise_pays_demand_rate_for_import_leaf(self, unused_mock):
        p2 = _ensure_type(
            type_id=9832,
            name="Coolant",
            group_id=1034,
            group_name="Refined Commodities - Tier 2",
            category_id=43,
            category_name="Planetary Commodities",
        )
        hull = _ensure_type(
            type_id=999012,
            name="Rate Hull",
            group_id=25,
            group_name="Frigate",
            category_id=6,
            category_name="Ship",
        )
        hull_bp = _ensure_type(
            type_id=999013,
            name="Rate Hull Blueprint",
            group_id=105,
            group_name="Blueprint",
            category_id=9,
            category_name="Blueprint",
        )
        EveIndustryActivityProduct.objects.create(
            eve_type=hull_bp,
            activity_id=1,
            product_eve_type=hull,
            quantity=1,
        )
        EveIndustryActivityMaterial.objects.create(
            eve_type=hull_bp,
            activity_id=1,
            material_eve_type=p2,
            quantity=5,
        )
        IndustryProduct.objects.create(eve_type=hull, strategy="imported")
        character = EveCharacter.objects.create(
            character_id=9102,
            character_name="Rate Tester",
        )
        order = IndustryOrder.objects.create(
            character=character,
            needed_by=timezone.now().date(),
            public_short_code="RAT",
        )
        IndustryOrderItem.objects.create(
            order=order, eve_type=hull, quantity=1
        )
        BuybackAcceptedItem.objects.create(
            eve_type=p2,
            category=BuybackAcceptedItem.Category.P2,
            demand_status=BuybackAcceptedItem.DemandStatus.HIGH,
            demand_quantity=5,
            metrics_updated_at=timezone.now(),
        )
        EveLocation.objects.create(
            location_id=60003760,
            location_name="Jita IV - Moon 4 - Caldari Navy Assembly Plant",
            solar_system_id=30000142,
            solar_system_name="Jita",
            short_name="Jita",
            region_id=10000002,
            price_baseline=True,
        )
        EveMarketItemHistory.objects.create(
            region_id=10000002,
            item=p2,
            date=date(2026, 7, 31),
            average=Decimal("9000.00"),
            highest=Decimal("10000.00"),
            lowest=Decimal("8000.00"),
            volume=10_000,
        )
        EveBuybackSettings.load()

        response = Client().post(
            f"{BASE_URL}/appraise",
            data={"paste": "Coolant\t2"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        line = data["lines"][0]
        self.assertTrue(line["accepted"])
        self.assertEqual(line["rate"], 1.0)
        self.assertEqual(line["rate_reason"], "supply_chain_import")
        self.assertEqual(data["offer_total"], 18000.0)
