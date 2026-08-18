from datetime import timedelta
from types import SimpleNamespace

from django.utils import timezone

from app.test import TestCase

from eveonline.models import EveLocation
from fittings.models import EveFitting
from market.helpers.contracts import (
    _map_contract_status,
    create_or_update_contract_from_db_contract,
)
from market.models import EveMarketContract


class MapContractStatusTestCase(TestCase):
    def test_active_statuses_map_to_outstanding(self):
        self.assertEqual("outstanding", _map_contract_status("outstanding"))
        self.assertEqual("outstanding", _map_contract_status("in_progress"))

    def test_finished_statuses_map_to_finished(self):
        self.assertEqual("finished", _map_contract_status("finished"))
        self.assertEqual("finished", _map_contract_status("finished_issuer"))
        self.assertEqual(
            "finished", _map_contract_status("finished_contractor")
        )

    def test_terminal_non_sale_statuses_map_to_expired(self):
        for status in (
            "expired",
            "deleted",
            "cancelled",
            "rejected",
            "failed",
            "reversed",
        ):
            self.assertEqual(
                "expired",
                _map_contract_status(status),
                msg=status,
            )

    def test_unknown_and_empty_map_to_expired(self):
        self.assertEqual("expired", _map_contract_status("weird_status"))
        self.assertEqual("expired", _map_contract_status(""))


class CreateOrUpdateContractFromDbContractStatusTestCase(TestCase):
    def setUp(self):
        self.location = EveLocation.objects.create(
            location_id=6001,
            location_name="Test Structure",
            solar_system_id=1,
            solar_system_name="Sys",
            short_name="tst",
            region_id=1,
            market_active=True,
        )
        self.fitting = EveFitting.objects.create(
            name="[FL33T] Deacon",
            eft_format="[Deacon, [FL33T] Deacon]",
            ship_id=37457,
        )

    def _db_contract(self, *, contract_id: int, status: str):
        return SimpleNamespace(
            contract_id=contract_id,
            type=EveMarketContract.esi_contract_type,
            start_location_id=self.location.location_id,
            title=self.fitting.name,
            status=status,
            price=35_000_000,
            issuer_id=862613217,
            date_issued=timezone.now() - timedelta(days=90),
            date_expired=timezone.now() - timedelta(days=60),
            date_completed=None,
            assignee_id=None,
            acceptor_id=None,
        )

    def test_deleted_source_contract_does_not_count_as_outstanding(self):
        self.assertTrue(
            create_or_update_contract_from_db_contract(
                self._db_contract(contract_id=230437067, status="deleted"),
                self.location,
            )
        )
        contract = EveMarketContract.objects.get(id=230437067)
        self.assertEqual("expired", contract.status)
        self.assertFalse(contract.is_public)

    def test_unknown_title_is_still_stored(self):
        db_contract = self._db_contract(
            contract_id=230437069, status="outstanding"
        )
        db_contract.title = "[FL33T] Torpedo"
        self.assertTrue(
            create_or_update_contract_from_db_contract(
                db_contract, self.location
            )
        )
        contract = EveMarketContract.objects.get(id=230437069)
        self.assertEqual("[FL33T] Torpedo", contract.title)
        self.assertEqual("outstanding", contract.status)
        self.assertIsNone(contract.fitting_id)

    def test_resync_keeps_deleted_contract_expired(self):
        EveMarketContract.objects.create(
            id=230437068,
            title=self.fitting.name,
            price=35_000_000,
            issuer_external_id=862613217,
            status="outstanding",
            fitting=self.fitting,
            location=self.location,
            is_public=False,
            expires_at=timezone.now() - timedelta(days=60),
        )
        self.assertTrue(
            create_or_update_contract_from_db_contract(
                self._db_contract(contract_id=230437068, status="deleted"),
                self.location,
            )
        )
        self.assertEqual(
            "expired", EveMarketContract.objects.get(id=230437068).status
        )
