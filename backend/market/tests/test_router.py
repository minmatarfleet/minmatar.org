from django.test import Client
from django.utils import timezone

from app.test import TestCase

from eveonline.models import EveCharacter, EveLocation
from fittings.models import EveFitting
from market.models import (
    EveMarketContract,
    EveMarketContractExpectation,
    EveMarketContractResponsibility,
)

BASE_URL = "/api/market"


class MarketRouterTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        super().setUp()

    def _setup_expecation(self):
        loc = EveLocation.objects.create(
            location_id=1234,
            location_name="Somewhere else",
            solar_system_id=1,
            solar_system_name="Somewhere",
            market_active=True,
        )
        fit = EveFitting.objects.create(
            name="[NVY-5] Atron",
            ship_id=1,
            description="Testing",
            eft_format="[Atron, [NVY-5] Atron]",
        )
        return EveMarketContractExpectation.objects.create(
            fitting=fit,
            location=loc,
            quantity=10,
        )

    def test_expectations_by_location(self):
        self._setup_expecation()

        response = self.client.get(f"{BASE_URL}/expectations/by-location")
        self.assertEqual(200, response.status_code)
        locations = response.json()
        self.assertEqual(1, len(locations))
        self.assertEqual(1, len(locations[0]["expectations"]))

    def test_get_contracts(self):
        expectation = self._setup_expecation()

        timestamp = timezone.now()

        EveMarketContract.objects.create(
            id=1234,
            location=expectation.location,
            fitting=expectation.fitting,
            status="outstanding",
            price=123.45,
            issuer_external_id=1,
            created_at=timestamp,
        )
        char = EveCharacter.objects.create(
            character_id=12345,
            character_name="Test Pilot",
        )
        EveMarketContractResponsibility.objects.create(
            expectation=expectation,
            entity_id=char.character_id,
        )

        response = self.client.get(
            f"{BASE_URL}/contracts?location_id={expectation.location.location_id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertEqual(1, len(data))
        self.assertEqual("[NVY-5] Atron", data[0]["title"])
        self.assertEqual(1, data[0]["current_quantity"])
        self.assertEqual(10, data[0]["desired_quantity"])
        self.assertIn(
            str(timestamp)[0:19], data[0]["latest_contract_timestamp"]
        )
        self.assertEqual(
            "Test Pilot", data[0]["responsibilities"][0]["entity_name"]
        )
        self.assertIn("doctrines", data[0])
        self.assertIsInstance(data[0]["doctrines"], list)

    def test_get_contracts_unknown_location_returns_empty(self):
        response = self.client.get(
            f"{BASE_URL}/contracts?location_id=999999",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual([], response.json())

    def test_get_contracts_includes_fittings_with_contracts_but_no_expectation(
        self,
    ):
        """Fittings that have contracts at the location but no expectation are still returned."""
        loc = EveLocation.objects.create(
            location_id=5555,
            location_name="Contract-only location",
            solar_system_id=1,
            solar_system_name="Somewhere",
            market_active=True,
        )
        fit = EveFitting.objects.create(
            name="[NVY-9] No Expectation",
            ship_id=2,
            description="No expectation",
            eft_format="[Merlin, [NVY-9] No Expectation]",
        )
        EveMarketContract.objects.create(
            id=9999,
            location=loc,
            fitting=fit,
            status="outstanding",
            price=1.0,
            issuer_external_id=1,
        )
        response = self.client.get(
            f"{BASE_URL}/contracts?location_id={loc.location_id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertEqual(1, len(data))
        self.assertEqual("[NVY-9] No Expectation", data[0]["title"])
        self.assertEqual(1, data[0]["current_quantity"])
        self.assertEqual(0, data[0]["desired_quantity"])
        self.assertIsNone(data[0]["expectation_id"])
        self.assertEqual([], data[0]["responsibilities"])
        self.assertEqual([], data[0]["doctrines"])

    def test_inactive_market(self):
        # Test that locations with market_active=False are not included
        # in market-related queries. This test verifies the location model
        # behavior rather than testing a removed endpoint.
        location_inactive = EveLocation.objects.create(
            location_id=1,
            location_name="Location 1",
            solar_system_id=1,
            solar_system_name="Solar 1",
            short_name="One",
            market_active=False,
        )
        location_active = EveLocation.objects.create(
            location_id=2,
            location_name="Location 2",
            solar_system_id=2,
            solar_system_name="Solar 2",
            short_name="Two",
            market_active=True,
        )

        self.assertFalse(location_inactive.market_active)
        self.assertTrue(location_active.market_active)

        active_locations = EveLocation.objects.filter(market_active=True)
        self.assertEqual(1, active_locations.count())
        self.assertEqual("Location 2", active_locations.first().location_name)
