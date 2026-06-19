"""Tests for GET /api/market/sell-orders."""

from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.db import connection

from app.test import TestCase
from eveonline.models import EveLocation
from eveuniverse.models import EveCategory, EveGroup, EveType

from market.models.item import EveMarketItemExpectation, EveMarketItemOrder


class GetSellOrdersEndpointTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.client = Client()
        cls.category, _ = EveCategory.objects.get_or_create(
            id=9201,
            defaults={"name": "Module", "published": True},
        )
        cls.group, _ = EveGroup.objects.get_or_create(
            id=9201,
            defaults={
                "name": "Ammo",
                "published": True,
                "eve_category": cls.category,
            },
        )
        cls.item_type, _ = EveType.objects.get_or_create(
            id=9201,
            defaults={
                "name": "Antimatter Charge S",
                "published": True,
                "eve_group": cls.group,
            },
        )

    def _create_location(self, location_id: int, name: str):
        return EveLocation.objects.create(
            location_id=location_id,
            location_name=name,
            short_name=name[:8],
            market_active=True,
            solar_system_id=1,
            solar_system_name="Test",
        )

    def test_get_sell_orders_query_count_stable_across_locations(self):
        location_a = self._create_location(92001, "Alpha Market")
        location_b = self._create_location(92002, "Beta Market")
        for location in (location_a, location_b):
            EveMarketItemExpectation.objects.create(
                item=self.item_type,
                location=location,
                quantity=100,
            )
            EveMarketItemOrder.objects.create(
                item=self.item_type,
                location=location,
                price="10.00",
                quantity=25,
            )

        with CaptureQueriesContext(connection) as context:
            response = self.client.get("/api/market/sell-orders")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(2, len(payload))
        self.assertLess(len(context.captured_queries), 15)
