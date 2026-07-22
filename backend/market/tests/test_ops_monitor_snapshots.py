from unittest.mock import patch

from django.test import Client

from app.test import TestCase
from eveonline.client import EsiResponse
from eveonline.models import EveLocation
from fittings.models import EveFitting
from market.helpers.ops_snapshot import (
    list_ops_monitor_snapshots,
    record_ops_monitor_snapshots,
)
from market.models import (
    EveMarketContract,
    EveMarketContractExpectation,
    EveMarketOpsMonitorSnapshot,
)
from market.tasks import (
    fetch_eve_market_contracts,
    fetch_structure_sell_orders,
)

BASE_URL = "/api/market"


class OpsMonitorSnapshotTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.loc = EveLocation.objects.create(
            location_id=99,
            location_name="Somewhere",
            short_name="Somewhere",
            solar_system_id=1,
            solar_system_name="Somewhere",
            market_active=True,
        )
        self.fit = EveFitting.objects.create(
            name="[NVY-5] Atron",
            ship_id=608,
            description="Testing",
            eft_format="[Atron, [NVY-5] Atron]",
        )
        EveMarketContractExpectation.objects.create(
            fitting=self.fit,
            location=self.loc,
            quantity=4,
        )
        EveMarketContract.objects.create(
            id=1,
            status="outstanding",
            title="Bad Title",
            price=1,
            issuer_external_id=1,
            location=self.loc,
            fitting=self.fit,
            match_score=0.5,
            match_is_flagged=False,
        )

    def test_record_snapshot_from_local_db(self):
        created = record_ops_monitor_snapshots(
            trigger=EveMarketOpsMonitorSnapshot.TRIGGER_CONTRACTS,
            location_id=self.loc.location_id,
        )
        self.assertEqual(created, 1)
        snap = EveMarketOpsMonitorSnapshot.objects.get()
        self.assertEqual(snap.location_id, self.loc.pk)
        self.assertEqual(
            snap.trigger, EveMarketOpsMonitorSnapshot.TRIGGER_CONTRACTS
        )
        self.assertIsNotNone(snap.contracts_health_pct)
        self.assertGreaterEqual(snap.understocked_contracts_count, 1)
        self.assertEqual(len(snap.understocked_contracts), 1)
        self.assertNotIn("eft_format", snap.understocked_contracts[0])
        self.assertEqual(
            snap.understocked_contracts[0]["fitting_name"], self.fit.name
        )

    def test_history_api_returns_snapshots(self):
        record_ops_monitor_snapshots(
            trigger=EveMarketOpsMonitorSnapshot.TRIGGER_ORDERS,
            location_id=self.loc.location_id,
        )
        response = self.client.get(
            f"{BASE_URL}/ops-monitor/history",
            {"location_id": self.loc.location_id},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["location_id"], self.loc.location_id)
        self.assertEqual(
            data[0]["trigger"], EveMarketOpsMonitorSnapshot.TRIGGER_ORDERS
        )
        self.assertIn("understocked_contracts", data[0])
        self.assertIn("sell_gaps", data[0])

    def test_list_snapshots_respects_limit(self):
        for _ in range(3):
            record_ops_monitor_snapshots(
                trigger=EveMarketOpsMonitorSnapshot.TRIGGER_CONTRACTS,
                location_id=self.loc.location_id,
            )
        rows = list_ops_monitor_snapshots(
            location_id=self.loc.location_id, limit=2
        )
        self.assertEqual(len(rows), 2)

    @patch("market.tasks.record_ops_monitor_snapshot_task")
    @patch("market.tasks.fetch_contract_items_task")
    @patch("market.tasks.EsiClient")
    def test_contract_sync_schedules_snapshot(
        self, esi_mock, items_task_mock, snapshot_task_mock
    ):
        self.loc.region_id = 100001
        self.loc.save(update_fields=["region_id"])
        esi_mock.return_value.get_public_contracts.return_value = EsiResponse(
            response_code=200,
            data=[],
        )

        fetch_eve_market_contracts()

        snapshot_task_mock.delay.assert_called_once_with(
            EveMarketOpsMonitorSnapshot.TRIGGER_CONTRACTS,
        )
        self.assertIsNotNone(items_task_mock)

    @patch("market.tasks.record_ops_monitor_snapshot_task")
    @patch("market.tasks.sync_structure_order_book_for_location")
    @patch("market.tasks.get_character_with_structure_markets_scope")
    def test_order_sync_schedules_snapshot_after_location(
        self, scope_mock, sync_mock, snapshot_task_mock
    ):
        scope_mock.return_value = 42
        sync_mock.return_value = (0, 10)

        fetch_structure_sell_orders()

        sync_mock.assert_called_once_with(42, self.loc.location_id)
        snapshot_task_mock.delay.assert_called_once_with(
            EveMarketOpsMonitorSnapshot.TRIGGER_ORDERS,
            self.loc.location_id,
        )
