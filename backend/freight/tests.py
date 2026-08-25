from datetime import timedelta
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth.models import User
from django.test import Client, RequestFactory
from django.utils import timezone

from app.test import TestCase

from eveonline.helpers.characters import set_primary_character
from eveonline.models import (
    EveCharacter,
    EveCorporation,
    EveCorporationContract,
    EveLocation,
)
from freight.helpers.pricing import STANDARD_MAX_M3
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
        self.assertEqual(routes[0]["route_type"], "rate")
        self.assertEqual(routes[0]["max_m3"], 350000)
        self.assertIsNone(routes[0]["max_collateral"])

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

    def test_fixed_freight_cost_flat_fee(self):
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
            route_type=EveFreightRoute.RouteType.FIXED,
            fixed_fee_millions=25,
            xl_fee_millions=10,
            max_m3=950000,
            max_collateral=5_000_000_000,
            isk_per_m3=999,  # ignored for fixed
            collateral_modifier=0.01,
        )

        response_a = self.client.get(
            f"{BASE_URL}/routes/{route.id}/cost?m3=10000&collateral=1000000",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        response_b = self.client.get(
            f"{BASE_URL}/routes/{route.id}/cost"
            f"?m3=500000&collateral=2000000000",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(200, response_a.status_code)
        self.assertEqual(200, response_b.status_code)
        # Under 350k m³: 25M + 1% of 1M collateral.
        self.assertEqual(25_000_000 + 10_000, response_a.json()["cost"])
        # Over 350k m³: 25M + 10M XL + 1% of 2B collateral.
        self.assertEqual(
            25_000_000 + 10_000_000 + 20_000_000, response_b.json()["cost"]
        )

        routes = self.client.get(
            f"{BASE_URL}/routes",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        ).json()
        self.assertEqual(1, len(routes))
        self.assertEqual(routes[0]["route_type"], "fixed")
        self.assertEqual(routes[0]["max_m3"], 950000)
        self.assertEqual(routes[0]["max_collateral"], 5_000_000_000)

    def test_fixed_freight_xl_fee_threshold(self):
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
            route_type=EveFreightRoute.RouteType.FIXED,
            fixed_fee_millions=25,
            xl_fee_millions=10,
            max_m3=950000,
            max_collateral=5_000_000_000,
        )

        def cost_at(m3):
            response = self.client.get(
                f"{BASE_URL}/routes/{route.id}/cost?m3={m3}&collateral=0",
                HTTP_AUTHORIZATION=f"Bearer {self.token}",
            )
            self.assertEqual(200, response.status_code)
            return response.json()["cost"]

        # The XL fee applies strictly above 350,000 m³.
        self.assertEqual(25_000_000, cost_at(STANDARD_MAX_M3 - 1))
        self.assertEqual(25_000_000, cost_at(STANDARD_MAX_M3))
        self.assertEqual(35_000_000, cost_at(STANDARD_MAX_M3 + 1))

    def test_fixed_freight_cost_without_xl_or_collateral_fees(self):
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
            route_type=EveFreightRoute.RouteType.FIXED,
            fixed_fee_millions=25,
            max_m3=950000,
            max_collateral=5_000_000_000,
        )

        response = self.client.get(
            f"{BASE_URL}/routes/{route.id}/cost"
            f"?m3=900000&collateral=4000000000",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        # Defaults of 0 leave the reward at the flat fee alone.
        self.assertEqual(200, response.status_code)
        self.assertEqual(25_000_000, response.json()["cost"])

    def test_fixed_freight_cost_rejects_over_max_m3(self):
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
            route_type=EveFreightRoute.RouteType.FIXED,
            fixed_fee_millions=10,
            max_m3=950000,
            max_collateral=5_000_000_000,
        )

        response = self.client.get(
            f"{BASE_URL}/routes/{route.id}/cost?m3=950001&collateral=1",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(400, response.status_code)
        self.assertIn("Volume", response.json()["detail"])

    def test_fixed_freight_cost_rejects_over_max_collateral(self):
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
            route_type=EveFreightRoute.RouteType.FIXED,
            fixed_fee_millions=10,
            max_m3=950000,
            max_collateral=5_000_000_000,
        )

        response = self.client.get(
            f"{BASE_URL}/routes/{route.id}/cost"
            f"?m3=100&collateral=5000000001",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(400, response.status_code)
        self.assertIn("Collateral", response.json()["detail"])


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

    def test_proxy_includes_contracts_synced_under_another_corp(self):
        """Assignee is MFL even if another corp's ESI ingest stored the row."""
        self._make_contract(contract_id=1)
        self._make_contract(contract_id=2, corporation=self.other_corp)
        self.assertEqual(FreightContract.objects.count(), 2)
        self.assertEqual(
            set(FreightContract.objects.values_list("contract_id", flat=True)),
            {1, 2},
        )

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
        # Avoid live ESI when EveCharacter rows are created in these tests.
        public_data = patch("eveonline.signals.update_character_public_data")
        public_data.start()
        self.addCleanup(public_data.stop)
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

    def test_get_contracts_history_includes_issuer_corp_ingest(self):
        issuer_corp = EveCorporation.objects.create(
            corporation_id=98733885,
            name="Ballah Inc.",
            ticker="BLH",
        )
        EveCorporationContract.objects.create(
            contract_id=235149960,
            corporation=issuer_corp,
            type=FREIGHT_CONTRACT_TYPE,
            status="finished",
            issuer_id=274643078,
            for_corporation=True,
            assignee_id=FREIGHT_CORPORATION_ID,
            acceptor_id=149027055,
            start_location_id=100001,
            end_location_id=100002,
            volume=2932,
            collateral=67000000000,
            reward=1100000000,
            date_issued=timezone.now() - timedelta(hours=1),
            date_completed=timezone.now(),
        )
        response = self.client.get(
            f"{BASE_URL}/contracts/history",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        self.assertIn(
            235149960,
            [row["contract_id"] for row in response.json()],
        )

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

    def test_get_active_contracts_uses_location_short_names(self):
        EveLocation.objects.create(
            location_id=60003760,
            location_name="Jita IV - Moon 4 - Caldari Navy Assembly Plant",
            short_name="Jita",
            solar_system_id=30000142,
            solar_system_name="Jita",
            freight_active=True,
        )
        EveLocation.objects.create(
            location_id=1022167642188,
            location_name="Amamake - 5 times nearly AT winners",
            short_name="Amamake",
            solar_system_id=30002053,
            solar_system_name="Amamake",
            freight_active=True,
            is_structure=True,
        )
        EveCorporationContract.objects.create(
            contract_id=77777,
            corporation=self.corp,
            type=FREIGHT_CONTRACT_TYPE,
            status="outstanding",
            issuer_id=99999,
            assignee_id=FREIGHT_CORPORATION_ID,
            start_location_id=60003760,
            end_location_id=1022167642188,
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
        self.assertEqual(data[0]["start_location_name"], "Jita")
        self.assertEqual(data[0]["end_location_name"], "Amamake")

    def test_get_contracts_history_csv(self):
        issuer = EveCharacter.objects.create(
            character_id=11111,
            character_name="Issuer Pilot",
            corporation_id=FREIGHT_CORPORATION_ID,
        )
        hauler = EveCharacter.objects.create(
            character_id=22222,
            character_name="Hauler Alt",
            corporation_id=FREIGHT_CORPORATION_ID,
        )
        EveLocation.objects.create(
            location_id=60003760,
            location_name="Jita IV - Moon 4 - Caldari Navy Assembly Plant",
            short_name="Jita",
            solar_system_id=30000142,
            solar_system_name="Jita",
            freight_active=True,
        )
        EveLocation.objects.create(
            location_id=1022167642188,
            location_name="Amamake - 5 times nearly AT winners",
            short_name="Amamake",
            solar_system_id=30002053,
            solar_system_name="Amamake",
            freight_active=True,
            is_structure=True,
        )
        issued = timezone.now() - timedelta(days=2)
        completed = timezone.now() - timedelta(days=1)
        EveCorporationContract.objects.create(
            contract_id=88888,
            corporation=self.corp,
            type=FREIGHT_CONTRACT_TYPE,
            status="finished",
            issuer_id=issuer.character_id,
            issuer_corporation_id=FREIGHT_CORPORATION_ID,
            assignee_id=FREIGHT_CORPORATION_ID,
            acceptor_id=hauler.character_id,
            start_location_id=60003760,
            end_location_id=1022167642188,
            volume=12345,
            collateral=5000000,
            reward=75000,
            date_issued=issued,
            date_accepted=issued,
            date_completed=completed,
            title="Test haul",
        )
        # Active contracts should not appear in history CSV.
        EveCorporationContract.objects.create(
            contract_id=88889,
            corporation=self.corp,
            type=FREIGHT_CONTRACT_TYPE,
            status="outstanding",
            issuer_id=issuer.character_id,
            assignee_id=FREIGHT_CORPORATION_ID,
            start_location_id=60003760,
            end_location_id=1022167642188,
            volume=1,
            collateral=1,
            reward=1,
            date_issued=timezone.now(),
        )

        response = self.client.get(
            f"{BASE_URL}/contracts/history/csv",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        self.assertIn("text/csv", response["Content-Type"])
        self.assertIn(
            "attachment; filename=",
            response["Content-Disposition"],
        )
        body = response.content.decode("utf-8")
        self.assertIn("contract_id", body)
        self.assertIn("start_location_short_name", body)
        self.assertIn("88888", body)
        self.assertIn("Jita", body)
        self.assertIn("Amamake", body)
        self.assertIn("Issuer Pilot", body)
        self.assertIn("Hauler Alt", body)
        self.assertIn("12345", body)
        self.assertNotIn("88889", body)

    def test_get_contracts_history_csv_requires_auth(self):
        response = self.client.get(f"{BASE_URL}/contracts/history/csv")
        self.assertEqual(401, response.status_code)

    def test_get_contracts_history_csv_corp_acceptor(self):
        EveLocation.objects.create(
            location_id=60003760,
            location_name="Jita IV - Moon 4 - Caldari Navy Assembly Plant",
            short_name="Jita",
            solar_system_id=30000142,
            solar_system_name="Jita",
            freight_active=True,
        )
        EveLocation.objects.create(
            location_id=1022167642188,
            location_name="Amamake - 5 times nearly AT winners",
            short_name="Amamake",
            solar_system_id=30002053,
            solar_system_name="Amamake",
            freight_active=True,
            is_structure=True,
        )
        EveCorporationContract.objects.create(
            contract_id=88890,
            corporation=self.corp,
            type=FREIGHT_CONTRACT_TYPE,
            status="finished",
            issuer_id=11111,
            assignee_id=FREIGHT_CORPORATION_ID,
            acceptor_id=FREIGHT_CORPORATION_ID,
            start_location_id=60003760,
            end_location_id=1022167642188,
            volume=10,
            collateral=10,
            reward=10,
            date_issued=timezone.now() - timedelta(days=1),
            date_completed=timezone.now(),
        )
        response = self.client.get(
            f"{BASE_URL}/contracts/history/csv",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        body = response.content.decode("utf-8")
        self.assertIn("88890", body)
        self.assertIn("Freight Corp", body)

    def test_in_progress_shows_acceptor_without_user_link(self):
        """Acceptor with EveCharacter but no User still appears as servicing."""
        acceptor = EveCharacter.objects.create(
            character_id=2124533412,
            character_name="Minmatar Logistics Partner",
        )
        EveCorporationContract.objects.create(
            contract_id=11111,
            corporation=self.corp,
            type=FREIGHT_CONTRACT_TYPE,
            status="in_progress",
            issuer_id=99999,
            assignee_id=FREIGHT_CORPORATION_ID,
            acceptor_id=acceptor.character_id,
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
        self.assertEqual(data[0]["status"], "in_progress")
        self.assertEqual(data[0]["completed_by_id"], 2124533412)
        self.assertEqual(
            data[0]["completed_by_character_name"],
            "Minmatar Logistics Partner",
        )

    def test_in_progress_prefers_primary_character_when_linked(self):
        acceptor = EveCharacter.objects.create(
            character_id=2123595176,
            character_name="A Busy Dad",
            user=self.user,
        )
        primary = EveCharacter.objects.create(
            character_id=93402996,
            character_name="Wynric Marsson",
            user=self.user,
        )
        set_primary_character(self.user, primary)
        EveCorporationContract.objects.create(
            contract_id=22222,
            corporation=self.corp,
            type=FREIGHT_CONTRACT_TYPE,
            status="in_progress",
            issuer_id=99999,
            assignee_id=FREIGHT_CORPORATION_ID,
            acceptor_id=acceptor.character_id,
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
        self.assertEqual(data[0]["completed_by_id"], 93402996)
        self.assertEqual(
            data[0]["completed_by_character_name"], "Wynric Marsson"
        )

    def test_in_progress_freight_corp_acceptor_shows_corp_name(self):
        EveCorporationContract.objects.create(
            contract_id=33333,
            corporation=self.corp,
            type=FREIGHT_CONTRACT_TYPE,
            status="in_progress",
            issuer_id=99999,
            assignee_id=FREIGHT_CORPORATION_ID,
            acceptor_id=FREIGHT_CORPORATION_ID,
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
        self.assertEqual(data[0]["completed_by_id"], None)
        self.assertEqual(
            data[0]["completed_by_character_name"], "Freight Corp"
        )

    def test_outstanding_without_acceptor_has_no_completed_by(self):
        EveCorporationContract.objects.create(
            contract_id=44444,
            corporation=self.corp,
            type=FREIGHT_CONTRACT_TYPE,
            status="outstanding",
            issuer_id=99999,
            assignee_id=FREIGHT_CORPORATION_ID,
            acceptor_id=0,
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
        self.assertEqual(data[0]["completed_by_id"], None)
        self.assertEqual(data[0]["completed_by_character_name"], None)


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


class FreightContractsStatsEndpointTestCase(TestCase):
    """Test GET /contracts/stats aggregate metrics."""

    def setUp(self):
        self.client = Client()
        super().setUp()
        # Avoid live ESI when EveCharacter rows are created in these tests.
        public_data = patch("eveonline.signals.update_character_public_data")
        public_data.start()
        self.addCleanup(public_data.stop)
        self.corp = EveCorporation.objects.create(
            corporation_id=FREIGHT_CORPORATION_ID,
            name="Freight Corp",
            ticker="FRT",
        )
        self.now = timezone.now()

    def _create_contract(self, **kwargs):
        defaults = {
            "corporation": self.corp,
            "type": FREIGHT_CONTRACT_TYPE,
            "assignee_id": FREIGHT_CORPORATION_ID,
            "issuer_id": 99999,
            "start_location_id": 100001,
            "end_location_id": 100002,
            "volume": 10000,
            "collateral": 1000000,
            "reward": 10000,
            "date_issued": self.now - timedelta(days=2),
        }
        defaults.update(kwargs)
        return EveCorporationContract.objects.create(**defaults)

    def test_stats_empty(self):
        response = self.client.get(
            f"{BASE_URL}/contracts/stats",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertEqual(data["active_count"], 0)
        self.assertIsNone(data["average_delivery_seconds"])
        self.assertEqual(data["active_haulers_count"], 0)
        self.assertEqual(data["window_days"], 30)

    def test_active_count_includes_outstanding_and_in_progress(self):
        self._create_contract(contract_id=1, status="outstanding")
        self._create_contract(contract_id=2, status="outstanding")
        self._create_contract(
            contract_id=3, status="in_progress", acceptor_id=1
        )
        self._create_contract(contract_id=4, status="finished", acceptor_id=2)
        response = self.client.get(
            f"{BASE_URL}/contracts/stats",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(response.json()["active_count"], 3)

    def test_average_delivery_seconds_last_30_days(self):
        issued = self.now - timedelta(hours=10)
        completed = self.now - timedelta(hours=4)
        self._create_contract(
            contract_id=10,
            status="finished",
            date_issued=issued,
            date_completed=completed,
            acceptor_id=111,
        )
        # Outside window — ignored for average
        self._create_contract(
            contract_id=11,
            status="finished",
            date_issued=self.now - timedelta(days=40),
            date_completed=self.now - timedelta(days=39),
            acceptor_id=111,
        )
        response = self.client.get(
            f"{BASE_URL}/contracts/stats",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        # 6 hours = 21600 seconds
        self.assertEqual(response.json()["average_delivery_seconds"], 21600)

    def test_average_delivery_seconds_averages_multiple(self):
        self._create_contract(
            contract_id=20,
            status="finished",
            date_issued=self.now - timedelta(hours=4),
            date_completed=self.now - timedelta(hours=2),
            acceptor_id=111,
        )
        self._create_contract(
            contract_id=21,
            status="finished",
            date_issued=self.now - timedelta(hours=8),
            date_completed=self.now - timedelta(hours=2),
            acceptor_id=111,
        )
        response = self.client.get(
            f"{BASE_URL}/contracts/stats",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        # (2h + 6h) / 2 = 4h = 14400s
        self.assertEqual(response.json()["average_delivery_seconds"], 14400)

    def test_active_haulers_counts_distinct_users(self):
        user_a = User.objects.create(username="hauler_a")
        user_b = User.objects.create(username="hauler_b")
        alt_a = EveCharacter.objects.create(
            character_id=1001,
            character_name="Alt A",
            user=user_a,
        )
        primary_a = EveCharacter.objects.create(
            character_id=1002,
            character_name="Primary A",
            user=user_a,
        )
        set_primary_character(user_a, primary_a)
        hauler_b = EveCharacter.objects.create(
            character_id=2001,
            character_name="Hauler B",
            user=user_b,
        )
        set_primary_character(user_b, hauler_b)

        # Same user via alt + primary finished contracts → 1 hauler
        self._create_contract(
            contract_id=30,
            status="finished",
            acceptor_id=alt_a.character_id,
            date_issued=self.now - timedelta(days=1),
            date_completed=self.now - timedelta(hours=1),
        )
        self._create_contract(
            contract_id=31,
            status="finished",
            acceptor_id=primary_a.character_id,
            date_issued=self.now - timedelta(days=1),
            date_completed=self.now - timedelta(hours=2),
        )
        # Second user currently in progress
        self._create_contract(
            contract_id=32,
            status="in_progress",
            acceptor_id=hauler_b.character_id,
            date_issued=self.now - timedelta(hours=5),
        )
        # Freight corp acceptor excluded
        self._create_contract(
            contract_id=33,
            status="in_progress",
            acceptor_id=FREIGHT_CORPORATION_ID,
            date_issued=self.now - timedelta(hours=1),
        )
        # Finished outside window, no in_progress → not counted
        other = User.objects.create(username="old_hauler")
        old_char = EveCharacter.objects.create(
            character_id=3001,
            character_name="Old Hauler",
            user=other,
        )
        set_primary_character(other, old_char)
        self._create_contract(
            contract_id=34,
            status="finished",
            acceptor_id=old_char.character_id,
            date_issued=self.now - timedelta(days=40),
            date_completed=self.now - timedelta(days=39),
        )

        response = self.client.get(
            f"{BASE_URL}/contracts/stats",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(response.json()["active_haulers_count"], 2)

    def test_active_haulers_counts_acceptor_without_user(self):
        EveCharacter.objects.create(
            character_id=4001,
            character_name="Orphan Hauler",
        )
        self._create_contract(
            contract_id=40,
            status="in_progress",
            acceptor_id=4001,
            date_issued=self.now - timedelta(hours=2),
        )
        response = self.client.get(
            f"{BASE_URL}/contracts/stats",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(response.json()["active_haulers_count"], 1)
