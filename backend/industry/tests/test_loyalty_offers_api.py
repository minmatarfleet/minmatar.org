"""Tests for public LP store offers API."""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import Client
from django.utils import timezone
from eveonline.models import EveLocation
from eveuniverse.models import EveCategory, EveGroup, EveType
from market.models import EveMarketItemHistory

from app.test import TestCase as AppTestCase
from industry.helpers.lp_store_offer_economics_rebuild import (
    rebuild_lp_store_offer_economics,
)
from industry.models import (
    IndustryLoyaltyPoint,
    IndustryLpStoreOffer,
    IndustryLpStoreOfferEconomics,
    IndustryLpStoreOfferRequiredItem,
)

TLIB_CORP_ID = 1000182
IMPERIAL_CORP_ID = 1000179
HULL_TYPE_ID = 17740
INPUT_TYPE_ID = 42424
JITA_REGION_ID = 10000002


class LoyaltyOffersApiTestCase(AppTestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        EveLocation.objects.create(
            location_id=60003760,
            location_name="Jita IV - Moon 4 - Caldari Navy Assembly Plant",
            solar_system_id=30000142,
            solar_system_name="Jita",
            short_name="Jita",
            region_id=JITA_REGION_ID,
            price_baseline=True,
            prices_active=True,
        )
        IndustryLoyaltyPoint.objects.update_or_create(
            corporation_id=TLIB_CORP_ID,
            defaults={
                "name": "Tribal Liberation Force",
                "default_isk_per_lp": 800,
                "is_active": True,
            },
        )
        IndustryLoyaltyPoint.objects.update_or_create(
            corporation_id=IMPERIAL_CORP_ID,
            defaults={
                "name": "24th Imperial Crusade",
                "default_isk_per_lp": 900,
                "is_active": True,
            },
        )
        category = EveCategory.objects.create(
            id=6, name="Ship", published=True
        )
        group = EveGroup.objects.create(
            id=27, name="Frigate", published=True, eve_category=category
        )
        self.hull = EveType.objects.create(
            id=HULL_TYPE_ID,
            name="Republic Fleet Firetail",
            published=True,
            eve_group=group,
        )
        self.input_type = EveType.objects.create(
            id=INPUT_TYPE_ID,
            name="LP Input Item",
            published=True,
            eve_group=group,
        )
        today = timezone.now().date()
        EveMarketItemHistory.objects.create(
            region_id=JITA_REGION_ID,
            item=self.hull,
            date=today - timedelta(days=1),
            average=Decimal("250000000"),
            highest=Decimal("260000000"),
            lowest=Decimal("240000000"),
            order_count=5,
            volume=20,
        )
        EveMarketItemHistory.objects.create(
            region_id=JITA_REGION_ID,
            item=self.input_type,
            date=today - timedelta(days=1),
            average=Decimal("1500000"),
            highest=Decimal("1600000"),
            lowest=Decimal("1400000"),
            order_count=10,
            volume=100,
        )
        self.offer_a = IndustryLpStoreOffer.objects.create(
            offer_id=2001,
            corporation_id=TLIB_CORP_ID,
            type_id=HULL_TYPE_ID,
            lp_cost=50_000,
            isk_cost=10_000_000,
            quantity=1,
        )
        self.offer_b = IndustryLpStoreOffer.objects.create(
            offer_id=2002,
            corporation_id=TLIB_CORP_ID,
            type_id=INPUT_TYPE_ID,
            lp_cost=1_000,
            isk_cost=0,
            quantity=1,
        )
        self.offer_imperial = IndustryLpStoreOffer.objects.create(
            offer_id=2003,
            corporation_id=IMPERIAL_CORP_ID,
            type_id=HULL_TYPE_ID,
            lp_cost=60_000,
            isk_cost=5_000_000,
            quantity=1,
        )
        IndustryLpStoreOfferRequiredItem.objects.create(
            offer=self.offer_a,
            type_id=INPUT_TYPE_ID,
            quantity=2,
        )
        with patch(
            "industry.helpers.lp_store_economics._amamake_manufacturing_costs",
            return_value=({}, {}),
        ):
            rebuild_lp_store_offer_economics()

    def test_offers_public_without_auth(self):
        response = self.client.get("/api/industry/loyalty/offers")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("items", body)
        self.assertIn("total", body)
        self.assertEqual(body["limit"], body["total"])
        self.assertEqual(body["offset"], 0)
        self.assertGreaterEqual(body["total"], 3)
        self.assertEqual(len(body["items"]), body["total"])

    def test_offers_filter_currency(self):
        response = self.client.get(
            f"/api/industry/loyalty/offers?currency={TLIB_CORP_ID}"
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["total"], 2)
        for item in body["items"]:
            self.assertEqual(item["corporation_id"], TLIB_CORP_ID)

    def test_offers_search_by_type_name(self):
        response = self.client.get("/api/industry/loyalty/offers?q=Firetail")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertGreaterEqual(body["total"], 1)
        names = [item["type_name"] for item in body["items"]]
        self.assertTrue(any("Firetail" in name for name in names))

    def test_offers_pagination(self):
        response = self.client.get(
            "/api/industry/loyalty/offers?limit=1&offset=0"
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["limit"], 1)
        self.assertEqual(len(body["items"]), 1)
        self.assertGreaterEqual(body["total"], 3)

        page2 = self.client.get(
            "/api/industry/loyalty/offers?limit=1&offset=1"
        )
        self.assertEqual(page2.status_code, 200)
        self.assertNotEqual(
            body["items"][0]["offer_id"],
            page2.json()["items"][0]["offer_id"],
        )

    def test_offers_economics_fields_present(self):
        response = self.client.get(
            f"/api/industry/loyalty/offers?currency={TLIB_CORP_ID}"
            f"&q={HULL_TYPE_ID}"
        )
        self.assertEqual(response.status_code, 200)
        items = response.json()["items"]
        self.assertTrue(items)
        item = next(
            (row for row in items if row["offer_id"] == 2001), items[0]
        )
        self.assertEqual(item["type_id"], HULL_TYPE_ID)
        self.assertIn("Firetail", item["type_name"])
        self.assertEqual(item["currency_name"], "Tribal Liberation Force")
        self.assertEqual(item["lp_cost"], 50_000)
        self.assertEqual(item["isk_cost"], 10_000_000)
        self.assertIn("LP Input Item", item["required_items_summary"])
        self.assertIsNotNone(item["jita_sell"])
        self.assertIn("conversion_isk_per_lp_sell", item)
        self.assertIn("conversion_isk_per_lp_avg_7d", item)
        self.assertIn("volume_30d", item)
        self.assertIn("updated_at", item)

    def test_offers_side_avg_7d_accepted(self):
        response = self.client.get(
            "/api/industry/loyalty/offers"
            "?side=avg_7d&ordering=-conversion_avg_7d"
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("items", body)
        if body["items"]:
            self.assertIn("conversion_isk_per_lp_avg_7d", body["items"][0])

    def test_offers_exclude_tags_param_accepted(self):
        response = self.client.get(
            "/api/industry/loyalty/offers?exclude_tags=1"
            "&exclude_supply_packages=1&exclude_chips=1&exclude_skins=1"
            "&exclude_blueprints=1"
            "&exclude_useless_offers=1&exclude_below_set_lp_price=1"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("items", response.json())

    def test_offers_exclude_blueprints(self):
        IndustryLpStoreOfferEconomics.objects.filter(
            offer=self.offer_a
        ).update(kind="blueprint")
        response = self.client.get(
            "/api/industry/loyalty/offers?exclude_blueprints=1"
            f"&currency={TLIB_CORP_ID}"
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        offer_ids = {item["offer_id"] for item in body["items"]}
        self.assertNotIn(2001, offer_ids)
        self.assertIn(2002, offer_ids)
