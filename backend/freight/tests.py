from django.test import Client

from app.test import TestCase

from eveonline.models import EveLocation
from freight.models import (
    EveFreightRoute,
    EveFreightRouteOption,
)

BASE_URL = "/api/freight"


class FreightRouterTestCase(TestCase):
    """Test cases for the freight router."""

    def setUp(self):
        # create test client
        self.client = Client()

        super().setUp()

    def test_freight_routes(self):
        loc1 = EveLocation.objects.create(
            location_id=1,
            location_name="Location 1",
            short_name="Loc1",
            solar_system_id=1,
            solar_system_name="System 1",
        )
        loc2 = EveLocation.objects.create(
            location_id=2,
            location_name="Location 2",
            short_name="Loc2",
            solar_system_id=2,
            solar_system_name="System 2",
        )
        EveFreightRoute.objects.create(
            origin_location=loc1,
            destination_location=loc2,
            bidirectional=False,
        )
        EveFreightRoute.objects.create(
            origin_location=loc2,
            destination_location=loc1,
            bidirectional=False,
            active=False,
        )
        response = self.client.get(
            f"{BASE_URL}/routes",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(200, response.status_code)
        routes = response.json()
        self.assertEqual(1, len(routes))

    def test_freight_cost(self):
        loc1 = EveLocation.objects.create(
            location_id=1,
            location_name="Location 1",
            short_name="Loc1",
            solar_system_id=1,
            solar_system_name="System 1",
        )
        loc2 = EveLocation.objects.create(
            location_id=2,
            location_name="Location 2",
            short_name="Loc2",
            solar_system_id=2,
            solar_system_name="System 2",
        )
        route = EveFreightRoute.objects.create(
            origin_location=loc1,
            destination_location=loc2,
            bidirectional=True,
        )
        option = EveFreightRouteOption.objects.create(
            route=route,
            base_cost=1000,
            collateral_modifier=0.25,
            maximum_m3=1000,
        )

        response = self.client.get(
            f"{BASE_URL}/routes/{route.id}/options/{option.id}/cost?collateral=2000",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(200, response.status_code)
        self.assertEqual(route.id, response.json()["route_id"])
        self.assertEqual(1000 + (0.25 * 2000), response.json()["cost"])
