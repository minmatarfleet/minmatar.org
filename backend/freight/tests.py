from django.test import Client
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
    EveFreightRouteOption,
    EveFreightContract,
)
from freight.tasks import update_contracts

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


class FreightTaskTestCase(TestCase):
    """Unit tests for freight management background tasks."""

    def test_update_freight_contracts(self):
        """Contracts are updated from EveCorporationContract (internal DB)."""
        corp = EveCorporation.objects.create(
            corporation_id=EveFreightContract.supported_corporation_id,
            name="Test Corp",
            ticker="TEST",
        )
        EveCorporationContract.objects.create(
            contract_id=12345,
            corporation=corp,
            type=EveFreightContract.expected_contract_type,
            status="outstanding",
            issuer_id=99999,
            assignee_id=EveFreightContract.supported_corporation_id,
            start_location_id=100001,
            end_location_id=100002,
            volume=10000,
            collateral=1000000,
            reward=10000,
            date_issued=timezone.now(),
        )

        update_contracts()

        self.assertEqual(1, EveFreightContract.objects.count())
        contract = EveFreightContract.objects.get(contract_id=12345)
        self.assertEqual(contract.status, "outstanding")
        self.assertEqual(contract.volume, 10000)
        self.assertEqual(contract.reward, 10000)
        # Location names fall back to "Structure" when not in EveStructure
        self.assertEqual(contract.start_location_name, "Structure")
        self.assertEqual(contract.end_location_name, "Structure")
        # issuer_id 99999 has no EveCharacter → issuer is None
        self.assertIsNone(contract.issuer_id)

    def test_update_freight_contracts_with_issuer(self):
        """When issuer character exists, EveFreightContract gets issuer set."""
        corp = EveCorporation.objects.create(
            corporation_id=EveFreightContract.supported_corporation_id,
            name="Test Corp",
            ticker="TEST",
        )
        issuer_char = EveCharacter.objects.create(
            character_id=88888,
            character_name="Contract Issuer",
        )
        EveCorporationContract.objects.create(
            contract_id=54321,
            corporation=corp,
            type=EveFreightContract.expected_contract_type,
            status="outstanding",
            issuer_id=issuer_char.character_id,
            assignee_id=EveFreightContract.supported_corporation_id,
            start_location_id=100001,
            end_location_id=100002,
            volume=5000,
            collateral=500000,
            reward=5000,
            date_issued=timezone.now(),
        )

        update_contracts()

        contract = EveFreightContract.objects.get(contract_id=54321)
        self.assertEqual(contract.issuer_id, issuer_char.id)
        self.assertEqual(contract.issuer.character_id, 88888)
        self.assertEqual(contract.issuer.character_name, "Contract Issuer")
