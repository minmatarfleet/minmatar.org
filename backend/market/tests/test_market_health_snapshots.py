from datetime import timedelta
from dataclasses import replace
from unittest.mock import Mock, patch

from django.test import Client
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from app.test import TestCase
from eveonline.client import EsiResponse
from eveonline.models import EveLocation
from fittings.models import EveFitting
from market.helpers.contract_health import build_contract_health
from market.helpers.health_snapshot import (
    CONTRACTS_KIND,
    get_contract_health,
    get_market_health,
    get_sell_order_health,
    record_contract_health_snapshots,
    record_sell_order_health_snapshots,
)
from market.helpers.sell_order_health import get_live_sell_order_supply
from market.models import (
    EveMarketContract,
    EveMarketContractExpectation,
    EveMarketHealthSnapshot,
)
from market.tasks import (
    fetch_eve_market_contracts,
    fetch_structure_sell_orders,
)

BASE_URL = "/api/market"


class MarketHealthSnapshotTestCase(TestCase):
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

    def test_record_contract_snapshot_from_local_db(self):
        created = record_contract_health_snapshots(
            location_id=self.loc.location_id,
        )
        self.assertEqual(created, 1)
        snap = EveMarketHealthSnapshot.objects.get()
        self.assertEqual(snap.location_id, self.loc.pk)
        self.assertEqual(snap.kind, EveMarketHealthSnapshot.KIND_CONTRACTS)
        self.assertIsNotNone(snap.health_pct)
        self.assertEqual(
            EveMarketHealthSnapshot.objects.filter(
                kind=EveMarketHealthSnapshot.KIND_SELL_ORDERS
            ).count(),
            0,
        )

    def test_record_sell_order_snapshot_only_writes_sell_kind(self):
        created = record_sell_order_health_snapshots(
            location_id=self.loc.location_id,
        )
        self.assertEqual(created, 1)
        self.assertEqual(
            EveMarketHealthSnapshot.objects.filter(
                kind=EveMarketHealthSnapshot.KIND_CONTRACTS
            ).count(),
            0,
        )
        self.assertEqual(
            EveMarketHealthSnapshot.objects.filter(
                kind=EveMarketHealthSnapshot.KIND_SELL_ORDERS
            ).count(),
            1,
        )

    def test_health_api_returns_latest_and_history(self):
        record_contract_health_snapshots(location_id=self.loc.location_id)
        record_sell_order_health_snapshots(location_id=self.loc.location_id)
        response = self.client.get(
            f"{BASE_URL}/health",
            {"location_id": self.loc.location_id, "days": 30},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsNotNone(data["contracts"]["latest"])
        self.assertEqual(
            data["contracts"]["latest"]["location_id"], self.loc.location_id
        )
        self.assertEqual(len(data["contracts"]["history"]), 1)
        self.assertIsNotNone(data["sell_orders"]["latest"])
        self.assertIn("chart", data)
        self.assertGreaterEqual(len(data["chart"]), 1)
        newest = data["chart"][0]
        self.assertEqual(
            set(newest),
            {
                "captured_at",
                "contracts_health_pct",
                "contracts_viability_pct",
                "sell_orders_health_pct",
                "sell_orders_viability_pct",
            },
        )
        self.assertIsNotNone(newest["contracts_health_pct"])

    def test_health_chart_as_of_joins_independent_timestamps(self):
        now = timezone.now()
        record_contract_health_snapshots(location_id=self.loc.location_id)
        c_snap = EveMarketHealthSnapshot.objects.get(
            kind=EveMarketHealthSnapshot.KIND_CONTRACTS
        )
        EveMarketHealthSnapshot.objects.filter(pk=c_snap.pk).update(
            captured_at=now - timedelta(hours=2),
            health_pct=80.0,
            viability_pct=70.0,
        )
        record_sell_order_health_snapshots(location_id=self.loc.location_id)
        s_snap = EveMarketHealthSnapshot.objects.get(
            kind=EveMarketHealthSnapshot.KIND_SELL_ORDERS
        )
        EveMarketHealthSnapshot.objects.filter(pk=s_snap.pk).update(
            captured_at=now - timedelta(hours=1),
            health_pct=60.0,
            viability_pct=50.0,
        )

        payload = get_market_health(location_id=self.loc.location_id)
        # Two distinct times; later point carries forward contract values.
        self.assertEqual(len(payload["chart"]), 2)
        newest = payload["chart"][0]
        oldest = payload["chart"][1]
        self.assertEqual(newest["sell_orders_health_pct"], 60.0)
        self.assertEqual(newest["contracts_health_pct"], 80.0)
        self.assertEqual(oldest["contracts_health_pct"], 80.0)
        self.assertIsNone(oldest["sell_orders_health_pct"])

    def test_empty_location_returns_empty_health_payload(self):
        response = self.client.get(
            f"{BASE_URL}/health",
            {"location_id": 999999},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsNone(data["contracts"]["latest"])
        self.assertEqual(data["contracts"]["history"], [])
        self.assertIsNone(data["sell_orders"]["latest"])
        self.assertEqual(data["sell_orders"]["history"], [])
        self.assertEqual(data["chart"], [])

    def test_history_downsamples_and_omits_problem_lists(self):
        now = timezone.now()
        for hours_ago in (1, 2, 5, 10, 20, 40, 80, 200, 400, 800):
            record_contract_health_snapshots(
                location_id=self.loc.location_id,
            )
            snap = (
                EveMarketHealthSnapshot.objects.filter(
                    kind=EveMarketHealthSnapshot.KIND_CONTRACTS,
                    location=self.loc,
                )
                .order_by("-id")
                .first()
            )
            EveMarketHealthSnapshot.objects.filter(pk=snap.pk).update(
                captured_at=now - timedelta(hours=hours_ago)
            )

        payload = get_contract_health(
            location_id=self.loc.location_id, days=30
        )
        # 30d window: drop the 800h (~33d) point; keep the rest (9).
        self.assertEqual(len(payload["history"]), 9)
        oldest = min(payload["history"], key=lambda r: r["captured_at"])
        self.assertGreaterEqual(
            parse_datetime(oldest["captured_at"]),
            now - timedelta(days=30),
        )
        for point in payload["history"]:
            self.assertIn("health_pct", point)

    def test_record_contract_for_all_locations_builds_once(self):
        other_loc = EveLocation.objects.create(
            location_id=100,
            location_name="Elsewhere",
            short_name="Elsewhere",
            solar_system_id=2,
            solar_system_name="Elsewhere",
            market_active=True,
        )
        other_fit = EveFitting.objects.create(
            name="[NVY-5] Rifter",
            ship_id=587,
            description="Testing",
            eft_format="[Rifter, [NVY-5] Rifter]",
        )
        EveMarketContractExpectation.objects.create(
            fitting=other_fit,
            location=other_loc,
            quantity=2,
        )

        build_mock = Mock(wraps=build_contract_health)
        with patch(
            "market.helpers.health_snapshot.CONTRACTS_KIND",
            replace(CONTRACTS_KIND, build=build_mock),
        ):
            created = record_contract_health_snapshots()

        self.assertEqual(created, 2)
        build_mock.assert_called_once_with(location_id=None)

        snap_by_loc = {
            snap.location_id: snap
            for snap in EveMarketHealthSnapshot.objects.filter(
                kind=EveMarketHealthSnapshot.KIND_CONTRACTS
            )
        }
        self.assertIsNotNone(snap_by_loc[self.loc.pk].health_pct)
        self.assertIsNotNone(snap_by_loc[other_loc.pk].health_pct)

    @patch("market.tasks.record_contract_health_snapshot_task")
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

        snapshot_task_mock.delay.assert_called_once_with()
        self.assertIsNotNone(items_task_mock)

    @patch("market.tasks.record_sell_order_health_snapshot_task")
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
            self.loc.location_id,
        )

    def test_get_market_health_helper_merges_both(self):
        record_contract_health_snapshots(location_id=self.loc.location_id)
        record_sell_order_health_snapshots(location_id=self.loc.location_id)
        payload = get_market_health(location_id=self.loc.location_id)
        self.assertIsNotNone(payload["contracts"]["latest"])
        self.assertIsNotNone(payload["sell_orders"]["latest"])
        self.assertGreaterEqual(len(payload["chart"]), 1)
        newest = payload["chart"][0]
        self.assertIsNotNone(newest["contracts_health_pct"])
        sell_only = get_sell_order_health(location_id=self.loc.location_id)
        self.assertEqual(
            sell_only["latest"]["id"], payload["sell_orders"]["latest"]["id"]
        )

    def test_live_sell_order_supply_api_returns_full_rows(self):
        response = self.client.get(
            f"{BASE_URL}/sell-order-supply",
            {"location_id": self.loc.location_id},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["location_id"], self.loc.location_id)
        self.assertIn("rows", data)
        live = get_live_sell_order_supply(location_id=self.loc.location_id)
        self.assertIsNotNone(live)
        self.assertEqual(len(data["rows"]), len(live["rows"]))
