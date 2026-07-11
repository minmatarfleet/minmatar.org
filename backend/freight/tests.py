from django.contrib import admin
from django.contrib.auth.models import User
from django.test import Client, RequestFactory
from django.utils import timezone

from app.test import TestCase

from eveonline.models import (
    EveCharacter,
    EveCorporation,
    EveCorporationContract,
    EveLocation,
)
from freight.models import (
    EveFreightRoute,
    FreightContract,
    FREIGHT_CORPORATION_ID,
    FREIGHT_CONTRACT_TYPE,
)

BASE_URL = "/api/freight"


class FreightRouterTestCase(TestCase):
    """Test cases for the freight router."""

    def setUp(self):
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
            isk_per_m3=100,
        )
        EveFreightRoute.objects.create(
            origin_location=loc2,
            destination_location=loc1,
            active=False,
        )
        response = self.client.get(
            f"{BASE_URL}/routes",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(200, response.status_code)
        routes = response.json()
        self.assertEqual(1, len(routes))
        self.assertIn("expiration_days", routes[0])
        self.assertIn("days_to_complete", routes[0])
        self.assertEqual(routes[0]["expiration_days"], 3)
        self.assertEqual(routes[0]["days_to_complete"], 3)

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
            isk_per_m3=100,
            collateral_modifier=0.25,
        )

        response = self.client.get(
            f"{BASE_URL}/routes/{route.id}/cost?m3=10&collateral=2000",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(200, response.status_code)
        self.assertEqual(route.id, response.json()["route_id"])
        # 100 * 10 + ceil(0.25 * 2000) = 1000 + 500 = 1500
        self.assertEqual(1500, response.json()["cost"])


class FreightContractProxyTestCase(TestCase):
    """Verify that FreightContract is a correct filtered view of EveCorporationContract."""

    def setUp(self):
        super().setUp()
        self.corp = EveCorporation.objects.create(
            corporation_id=FREIGHT_CORPORATION_ID,
            name="Freight Corp",
            ticker="FRT",
        )
        self.other_corp = EveCorporation.objects.create(
            corporation_id=12345,
            name="Other Corp",
            ticker="OTH",
        )

    def _make_contract(self, corporation=None, **overrides):
        defaults = {
            "corporation": corporation or self.corp,
            "type": FREIGHT_CONTRACT_TYPE,
            "status": "outstanding",
            "issuer_id": 99999,
            "assignee_id": FREIGHT_CORPORATION_ID,
            "start_location_id": 100001,
            "end_location_id": 100002,
            "volume": 10000,
            "collateral": 1000000,
            "reward": 10000,
            "date_issued": timezone.now(),
        }
        defaults.update(overrides)
        return EveCorporationContract.objects.create(**defaults)

    def test_proxy_filters_to_freight_corporation(self):
        self._make_contract(contract_id=1)
        self._make_contract(contract_id=2, corporation=self.other_corp)
        self.assertEqual(FreightContract.objects.count(), 1)
        self.assertEqual(FreightContract.objects.first().contract_id, 1)

    def test_proxy_filters_to_courier_type(self):
        self._make_contract(contract_id=1)
        self._make_contract(contract_id=2, type="item_exchange")
        self.assertEqual(FreightContract.objects.count(), 1)

    def test_proxy_filters_to_assignee(self):
        self._make_contract(contract_id=1)
        self._make_contract(contract_id=2, assignee_id=77777)
        self.assertEqual(FreightContract.objects.count(), 1)

    def test_active_queryset(self):
        self._make_contract(contract_id=1, status="outstanding")
        self._make_contract(contract_id=2, status="in_progress")
        self._make_contract(contract_id=3, status="finished")
        self._make_contract(contract_id=4, status="expired")
        self.assertEqual(FreightContract.objects.active().count(), 2)

    def test_finished_queryset(self):
        self._make_contract(contract_id=1, status="outstanding")
        self._make_contract(contract_id=2, status="finished")
        self._make_contract(contract_id=3, status="finished")
        self.assertEqual(FreightContract.objects.finished().count(), 2)


class FreightContractsEndpointTestCase(TestCase):
    """Test the /contracts endpoint returns data from EveCorporationContract."""

    def setUp(self):
        self.client = Client()
        super().setUp()
        self.corp = EveCorporation.objects.create(
            corporation_id=FREIGHT_CORPORATION_ID,
            name="Freight Corp",
            ticker="FRT",
        )

    def test_get_active_contracts(self):
        EveCorporationContract.objects.create(
            contract_id=12345,
            corporation=self.corp,
            type=FREIGHT_CONTRACT_TYPE,
            status="outstanding",
            issuer_id=99999,
            assignee_id=FREIGHT_CORPORATION_ID,
            start_location_id=100001,
            end_location_id=100002,
            volume=10000,
            collateral=1000000,
            reward=10000,
            date_issued=timezone.now(),
        )
        response = self.client.get(
            f"{BASE_URL}/contracts",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["contract_id"], 12345)
        self.assertEqual(data[0]["status"], "outstanding")
        self.assertEqual(data[0]["volume"], 10000)

    def test_get_active_contracts_with_issuer(self):
        issuer = EveCharacter.objects.create(
            character_id=88888,
            character_name="Contract Issuer",
        )
        EveCorporationContract.objects.create(
            contract_id=54321,
            corporation=self.corp,
            type=FREIGHT_CONTRACT_TYPE,
            status="outstanding",
            issuer_id=issuer.character_id,
            assignee_id=FREIGHT_CORPORATION_ID,
            start_location_id=100001,
            end_location_id=100002,
            volume=5000,
            collateral=500000,
            reward=5000,
            date_issued=timezone.now(),
        )
        response = self.client.get(
            f"{BASE_URL}/contracts",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["issuer_id"], 88888)
        self.assertEqual(data[0]["issuer_character_name"], "Contract Issuer")


class FreightAdminViewsTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.admin_user = User.objects.create_superuser(
            username="freight_admin",
            email="freight@example.com",
            password="password",
        )
        self.client.force_login(self.admin_user)
        self.origin = EveLocation.objects.create(
            location_id=1001,
            location_name="Origin Hub",
            short_name="ORG",
            solar_system_id=1,
            solar_system_name="System A",
            freight_active=True,
        )
        self.destination = EveLocation.objects.create(
            location_id=1002,
            location_name="Destination Hub",
            short_name="DST",
            solar_system_id=2,
            solar_system_name="System B",
            freight_active=True,
        )
        EveFreightRoute.objects.create(
            origin_location=self.origin,
            destination_location=self.destination,
            isk_per_m3=50,
            active=True,
        )

    def test_freight_locations_view_lists_active_locations(self):
        response = self.client.get("/admin/freight/locations/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Freight locations")
        self.assertContains(response, "Origin Hub")
        self.assertContains(response, "Destination Hub")

    def test_freight_location_hub_view(self):
        response = self.client.get(
            f"/admin/freight/location/{self.origin.pk}/"
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Outbound routes")
        self.assertContains(response, "Manage outbound routes")
        self.assertContains(response, "Add outbound route")

    def test_get_app_list_shows_freight_locations_on_staging_systems(self):
        request = RequestFactory().get("/admin/")
        request.user = self.admin_user
        app_list = admin.site.get_app_list(request)
        staging = next(
            app for app in app_list if app["name"] == "Staging Systems"
        )
        names = [model["name"] for model in staging["models"]]
        self.assertIn("Freight locations", names)
        self.assertIn("Eve locations", names)

    def test_get_app_list_hides_eve_freight_route_from_supply(self):
        request = RequestFactory().get("/admin/")
        request.user = self.admin_user
        app_list = admin.site.get_app_list(request)
        supply = next(app for app in app_list if app["name"] == "Supply")
        keys = [model["object_name"].lower() for model in supply["models"]]
        self.assertNotIn("evefreightroute", keys)
