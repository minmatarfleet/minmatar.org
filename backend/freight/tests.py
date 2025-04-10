from django.test import Client

from app.test import TestCase

from freight.models import (
    EveFreightLocation,
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

    def test_freight_cost(self):
        loc1 = EveFreightLocation.objects.create(
            location_id=1,
            name="Location 1",
            short_name="Loc1",
        )
        loc2 = EveFreightLocation.objects.create(
            location_id=2,
            name="Location 2",
            short_name="Loc2",
        )
        route = EveFreightRoute.objects.create(
            orgin=loc1,
            destination=loc2,
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
