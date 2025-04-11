from django.test import Client

from app.test import TestCase

from fittings.models import EveFitting
from market.models import EveMarketLocation, EveMarketContractExpectation

BASE_URL = "/api/market"


class MarketRouterTestCase(TestCase):
    """Test cases for the market router."""

    def setUp(self):
        # create test client
        self.client = Client()

        super().setUp()

    def test_expectations_and_location(self):
        loc = EveMarketLocation.objects.create(
            location_id=1234,
            location_name="Somewhere else",
            solar_system_id=1,
            solar_system_name="Somewhere",
        )
        fit = EveFitting.objects.create(
            name="[NVY-5] Atron",
            ship_id=1,
            description="Testing",
            eft_format="[Atron, [NVY-5] Atron]",
        )
        EveMarketContractExpectation.objects.create(
            fitting=fit,
            location=loc,
            quantity=10,
        )

        response = self.client.get(
            f"{BASE_URL}/expectations",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        expectations = response.json()
        self.assertEqual(1, len(expectations))

        response = self.client.get(
            f"{BASE_URL}/locations",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        expectations = response.json()
        self.assertEqual(1, len(expectations))
        self.assertEqual("Somewhere else", expectations[0]["name"])
