from unittest.mock import patch

from django.test import Client
from django.utils import timezone
from django.db.models import signals

from app.test import TestCase

from fittings.models import EveFitting
from esi.models import Token
from eveonline.client import EsiResponse
from eveonline.models import EveCharacter
from eveonline.scopes import add_scopes, TokenType
from market.models import (
    EveMarketContract,
    EveMarketLocation,
    EveMarketContractExpectation,
)
from market.helpers import create_character_market_contracts

BASE_URL = "/api/market"


class MarketRouterTestCase(TestCase):
    """Test cases for the market router."""

    def setUp(self):
        # create test client
        self.client = Client()

        super().setUp()

    def _setup_expecation(self):
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
        location = EveMarketLocation.objects.create(
            location_id=1,
            location_name="Test",
            solar_system_id=1,
            solar_system_name="Jita",
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
