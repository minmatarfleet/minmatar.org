import factory
from datetime import timedelta
from unittest.mock import patch

from django.test import Client
from django.utils import timezone
from django.db.models import signals

from app.test import TestCase

from fittings.models import EveFitting
from esi.models import Token
from eveonline.client import EsiResponse
from eveonline.models import EveCorporation, EveCharacter, EveLocation
from eveonline.scopes import add_scopes, TokenType
from market.models import (
    EveMarketContract,
    EveMarketContractExpectation,
)
from market.helpers import (
    create_character_market_contracts,
    create_corporation_market_contracts,
)
from market.tasks import (
    fetch_eve_public_contracts,
    get_fitting_for_contract,
)

BASE_URL = "/api/market"


class MarketRouterTestCase(TestCase):
    """Test cases for the market router."""

    def setUp(self):
        # create test client
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

    def test_expectations_and_location(self):
        self._setup_expecation()

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

        response = self.client.get(
            f"{BASE_URL}/contracts",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertEqual(1, len(data))
        self.assertEqual("[NVY-5] Atron", data[0]["title"])
        self.assertEqual(1, data[0]["current_quantity"])
        self.assertIn(
            str(timestamp)[0:19], data[0]["latest_contract_timestamp"]
        )

    def test_inactive_market(self):
        EveLocation.objects.create(
            location_id=1,
            location_name="Location 1",
            solar_system_id=1,
            solar_system_name="Solar 1",
            short_name="One",
            market_active=False,
        )
        EveLocation.objects.create(
            location_id=2,
            location_name="Location 2",
            solar_system_id=2,
            solar_system_name="Solar 2",
            short_name="Two",
            market_active=True,
        )

        response = self.client.get(
            f"{BASE_URL}/locations",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertEqual(1, len(data))
        self.assertEqual("Solar 2", data[0]["system_name"])


class MarketHelperTestCase(TestCase):
    """Tests of the market helper functions."""

    def setUp(self):
        signals.post_save.disconnect(
            sender=EveCharacter,
            dispatch_uid="populate_eve_character_public_data",
        )
        signals.post_save.disconnect(
            sender=EveCharacter,
            dispatch_uid="populate_eve_character_private_data",
        )

        super().setUp()

    def test_create_character_market_contracts(self):
        token = Token.objects.create(
            user=self.user,
            character_id=1234,
            character_name="Tester",
        )
        add_scopes(TokenType.MARKET, token)
        char = EveCharacter.objects.create(
            character_id=token.character_id,
            character_name=token.character_name,
            token=token,
        )
        location = EveLocation.objects.create(
            location_id=1,
            location_name="Test",
            solar_system_id=1,
            solar_system_name="Jita",
            market_active=True,
        )
        fitting = EveFitting.objects.create(
            name="[NVY-5] Atron",
            ship_id=1,
            description="Testing",
            eft_format="[Atron, [NVY-5] Atron]",
        )
        with patch("market.helpers.EsiClient") as mock:
            contact_id = 1234
            instance = mock.return_value
            instance.get_character_contracts.return_value = EsiResponse(
                response_code=200,
                data=[
                    {
                        "contract_id": contact_id,
                        "type": "item_exchange",
                        "status": "outstanding",
                        "issuer_id": char.character_id,
                        "title": fitting.name,
                        "start_location_id": location.location_id,
                        "price": 12.34,
                        "for_corporation": False,
                        "acceptor_id": 0,
                        "assignee_id": None,
                        "date_completed": None,
                    }
                ],
            )

            create_character_market_contracts(char.character_id)

            contract = EveMarketContract.objects.filter(id=contact_id).first()
            self.assertIsNotNone(contract)
            self.assertEqual(fitting.name, contract.title)

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    @patch("market.helpers.EsiClient")
    def test_create_corporation_market_contracts(self, esi_mock):
        esi = esi_mock.return_value

        token = Token.objects.create(
            user=self.user,
            character_id=1234,
            character_name="Tester",
        )
        add_scopes(TokenType.MARKET, token)
        char = EveCharacter.objects.create(
            character_id=token.character_id,
            character_name=token.character_name,
            token=token,
        )
        location = EveLocation.objects.create(
            location_id=1,
            location_name="Test",
            solar_system_id=1,
            solar_system_name="Jita",
            market_active=True,
        )
        fitting = EveFitting.objects.create(
            name="[NVY-5] Atron",
            ship_id=1,
            description="Testing",
            eft_format="[Atron, [NVY-5] Atron]",
        )
        corp = EveCorporation.objects.create(
            corporation_id=10001,
            name="Megacorp",
            ceo=char,
        )

        contract_id = 2345
        esi.get_corporation_contracts.return_value = EsiResponse(
            response_code=200,
            data=[
                {
                    "contract_id": contract_id,
                    "type": "item_exchange",
                    "status": "outstanding",
                    "issuer_id": corp.corporation_id,
                    "title": fitting.name,
                    "start_location_id": location.location_id,
                    "price": 12.34,
                    "for_corporation": True,
                    "acceptor_id": 0,
                    "assignee_id": None,
                    "date_completed": None,
                }
            ],
        )

        create_corporation_market_contracts(corp.corporation_id)

        contract = EveMarketContract.objects.filter(id=contract_id).first()
        self.assertIsNotNone(contract)
        self.assertEqual(fitting.name, contract.title)


class MarketTaskTestCase(TestCase):
    """Test cases for the market tasks."""

    @patch("market.tasks.EsiClient")
    def test_fetch_eve_public_contracts(self, esi_mock):

        location = EveLocation.objects.create(
            location_id=1001,
            location_name="Home base",
            market_active=True,
            region_id=100001,
            solar_system_id=100002,
        )
        fitting = EveFitting.objects.create(
            name="[FL33T] Thrasher",
            eft_format="[Thrasher, [FL33T] Thrasher]",
            ship_id=1001,
        )

        esi = esi_mock.return_value
        esi.get_public_contracts.return_value = EsiResponse(
            response_code=200,
            data=[
                {
                    "contract_id": 10000001,
                    "type": EveMarketContract.esi_contract_type,
                    "start_location_id": location.location_id,
                    "date_expired": timezone.now() + timedelta(days=30),
                    "title": fitting.name,
                    "status": "outstanding",
                    "price": 12.34,
                    "issuer_id": 1,
                    "assignee_id": None,
                    "acceptor_id": None,
                },
                {
                    "contract_id": 10000002,
                    "type": EveMarketContract.esi_contract_type,
                    "start_location_id": location.location_id,
                    "date_expired": timezone.now() + timedelta(days=30),
                    "title": "Random contract",
                    "status": "outstanding",
                    "price": 12.34,
                    "issuer_id": 1,
                    "assignee_id": None,
                    "acceptor_id": None,
                },
            ],
        )

        fetch_eve_public_contracts()

        contracts = EveMarketContract.objects.all()

        self.assertEqual(1, contracts.count())
        self.assertEqual(10000001, contracts[0].id)
        self.assertEqual(fitting.id, contracts[0].fitting.id)
        self.assertEqual(
            location.location_id, contracts[0].location.location_id
        )

    def test_get_fitting_id_for_contract(self):
        fitting = EveFitting.objects.create(
            name="[FL33T] Thrasher",
            eft_format="[Thrasher, [FL33T] Thrasher]",
            ship_id=1001,
            aliases="[NVY-5] Thrasher,[L3ARN] Thrasher",
        )

        self.assertEquals(
            fitting, get_fitting_for_contract("[FL33T] Thrasher")
        )
        self.assertEquals(
            fitting, get_fitting_for_contract("[fl33t] thrasher")
        )
        self.assertEquals(
            fitting, get_fitting_for_contract("[NVY-5] Thrasher")
        )
        self.assertEquals(
            fitting, get_fitting_for_contract("[FLEET] Thrasher")
        )

        self.assertIsNone(get_fitting_for_contract(None))
        self.assertIsNone(get_fitting_for_contract(""))
        self.assertIsNone(get_fitting_for_contract("[FL33T] Stabber"))
        self.assertIsNone(get_fitting_for_contract("Thrasher"))
