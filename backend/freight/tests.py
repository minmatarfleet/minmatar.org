from django.test import Client

from app.test import TestCase

from eveonline.models import EveLocation
from freight.models import (
    EveFreightLocation,
    EveFreightRoute,
    EveFreightRouteOption,
)
from freight.tasks import update_route_locations

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

    def test_update_route_locations(self):
        home = EveFreightLocation.objects.create(
            location_id=1001,
            name="Home",
            short_name="Home",
        )
        away = EveFreightLocation.objects.create(
            location_id=1002,
            name="Away",
            short_name="Away",
        )

        EveLocation.objects.create(
            location_id=1001,
            location_name="Home",
            short_name="Home",
            solar_system_id=2001,
            solar_system_name="Home",
            freight_active=True,
        )
        EveLocation.objects.create(
            location_id=1002,
            location_name="Away",
            short_name="Away",
            solar_system_id=2002,
            solar_system_name="Away",
            freight_active=True,
        )

        route = EveFreightRoute.objects.create(
            orgin=home,
            destination=away,
        )

        updated = update_route_locations()

        self.assertEqual(1, updated)

        route2 = EveFreightRoute.objects.get(id=route.id)
        self.assertEqual(2001, route2.origin_location.solar_system_id)
        self.assertEqual(2002, route2.destination_location.solar_system_id)

        updated_2 = update_route_locations()

        self.assertEqual(0, updated_2)
