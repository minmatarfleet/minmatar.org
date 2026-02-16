from datetime import timedelta
from unittest.mock import patch

from django.utils import timezone

from app.test import TestCase

from eveonline.models import (
    EveAlliance,
    EveCharacter,
    EveCorporation,
    EveLocation,
)
from eveonline.client import EsiResponse
from fittings.models import EveFitting
from market.models import EveMarketContract, EveMarketContractError
from market.tasks import (
    fetch_eve_public_contracts,
    get_fitting_for_contract,
    update_completed_contracts,
    update_expired_contracts,
)


class MarketTaskTestCase(TestCase):
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
        corp = EveCorporation.objects.create(
            corporation_id=1001,
            alliance=EveAlliance.objects.create(
                alliance_id=1002, ticker="BUILD"
            ),
        )
        seller = EveCharacter.objects.create(
            character_id=1,
            character_name="Seller",
            corporation_id=corp.corporation_id,
        )

        esi = esi_mock.return_value
        esi.get_public_contracts.return_value = EsiResponse(
            response_code=200,
            data=[
                {
                    "contract_id": 10000001,
                    "type": EveMarketContract.esi_contract_type,
                    "start_location_id": location.location_id,
                    "date_issued": timezone.now() - timedelta(days=10),
                    "date_expired": timezone.now() + timedelta(days=20),
                    "title": fitting.name,
                    "price": 12.34,
                    "issuer_id": seller.character_id,
                },
                {
                    "contract_id": 10000002,
                    "type": EveMarketContract.esi_contract_type,
                    "start_location_id": location.location_id,
                    "date_expired": timezone.now() + timedelta(days=30),
                    "title": "Random contract",
                    "price": 12.34,
                    "issuer_id": seller.character_id,
                },
                {
                    "contract_id": 10000003,
                    "type": EveMarketContract.esi_contract_type,
                    "start_location_id": location.location_id + 1,
                    "date_expired": timezone.now() + timedelta(days=30),
                    "title": "Random contract",
                    "price": 12.34,
                    "issuer_id": seller.character_id,
                },
                {
                    "contract_id": 10000004,
                    "type": "courier",
                    "start_location_id": location.location_id + 1,
                    "date_expired": timezone.now() + timedelta(days=30),
                    "title": "Random contract",
                    "price": 12.34,
                    "issuer_id": seller.character_id,
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

        contract_errors = EveMarketContractError.objects.all()
        self.assertEqual(1, contract_errors.count())
        self.assertEqual("Random contract", contract_errors.first().title)
        self.assertEqual(
            "Seller", contract_errors.first().issuer.character_name
        )

    def test_get_fitting_id_for_contract(self):
        fitting = EveFitting.objects.create(
            name="[FL33T] Thrasher",
            eft_format="[Thrasher, [FL33T] Thrasher]",
            ship_id=1001,
            aliases="[NVY-5] Thrasher,[L3ARN] Thrasher",
        )

        self.assertEqual(fitting, get_fitting_for_contract("[FL33T] Thrasher"))
        self.assertEqual(fitting, get_fitting_for_contract("[fl33t] thrasher"))
        self.assertEqual(fitting, get_fitting_for_contract("[NVY-5] Thrasher"))
        self.assertEqual(fitting, get_fitting_for_contract("[FLEET] Thrasher"))

        self.assertIsNone(get_fitting_for_contract(None))
        self.assertIsNone(get_fitting_for_contract(""))
        self.assertIsNone(get_fitting_for_contract("[FL33T] Stabber"))
        self.assertIsNone(get_fitting_for_contract("Thrasher"))

    def test_update_completed_contracts(self):
        cutoff = timezone.now()

        EveMarketContract.objects.create(
            id=10001,
            title="Should be marked complete",
            price=12.34,
            issuer_external_id=10001,
            status="outstanding",
            is_public=True,
            expires_at=cutoff + timedelta(days=1),
            last_updated=cutoff - timedelta(hours=1),
        )
        EveMarketContract.objects.create(
            id=10002,
            title="Updated after cutoff",
            price=12.34,
            issuer_external_id=1,
            status="outstanding",
            is_public=True,
            expires_at=cutoff + timedelta(days=1),
            last_updated=cutoff + timedelta(seconds=10),
        )
        EveMarketContract.objects.create(
            id=10003,
            title="Expired before cutoff",
            price=12.34,
            issuer_external_id=1,
            status="outstanding",
            is_public=True,
            expires_at=cutoff - timedelta(hours=1),
        )

        completed = update_completed_contracts(cutoff)

        self.assertEqual(1, completed)
        self.assertEqual(
            "finished", EveMarketContract.objects.get(id=10001).status
        )

        expired = update_expired_contracts(cutoff)

        self.assertEqual(1, expired)
        self.assertEqual(
            "expired", EveMarketContract.objects.get(id=10003).status
        )
