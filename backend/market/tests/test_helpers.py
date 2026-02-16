from unittest.mock import patch

from django.db.models import signals

from app.test import TestCase

from esi.models import Token
from eveonline.client import EsiResponse
from eveonline.models import EveCharacter, EveCorporation, EveLocation
from eveonline.scopes import add_scopes, TokenType
from fittings.models import EveFitting
from market.helpers import (
    create_character_market_contracts,
    create_corporation_market_contracts,
)
from market.models import EveMarketContract


class MarketHelperTestCase(TestCase):
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
        with patch("market.helpers.contracts.EsiClient") as mock:
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

    def test_create_corporation_market_contracts(self):
        with patch("market.helpers.contracts.EsiClient") as esi_mock:
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
